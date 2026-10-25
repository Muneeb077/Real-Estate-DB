"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import type { DateRange } from "react-day-picker";
import { toast } from "sonner";

import { DateRangePicker, isoDate } from "@/components/search/date-range-picker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errorMessage } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { money } from "@/lib/format";
import type { ListingDetail } from "@/lib/types";

type Quote = { nights: number; subtotal: number; service_fee: number; total: number; available: boolean; reason: string | null; currency: string };

export function BookingWidget({ listing }: { listing: ListingDetail }) {
  const { data: me } = useMe();
  const router = useRouter();
  const [range, setRange] = useState<DateRange | undefined>();
  const [guests, setGuests] = useState(1);
  // one key per reservation attempt: a double click or retry can't create two holds
  const idemKey = useRef(crypto.randomUUID());

  const { data: avail } = useQuery({
    queryKey: ["availability", listing.public_id],
    queryFn: () => api<{ unavailable: string[] }>(`/listings/${listing.public_id}/availability`),
  });
  const blocked = useMemo(() => new Set(avail?.unavailable ?? []), [avail]);

  const ready = range?.from && range?.to;
  const qs = ready ? `check_in=${isoDate(range.from)}&check_out=${isoDate(range.to)}&guests=${guests}` : "";
  const { data: quote, isFetching } = useQuery({
    queryKey: ["quote", listing.public_id, qs],
    queryFn: () => api<Quote>(`/listings/${listing.public_id}/quote?${qs}`),
    enabled: !!ready,
  });

  const reserve = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/v1/listings/${listing.public_id}/bookings`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idemKey.current,
          "X-CSRF-Token": document.cookie.match(/hn_csrf=([^;]+)/)?.[1] ?? "",
        },
        body: JSON.stringify({ check_in: isoDate(range!.from), check_out: isoDate(range!.to), guests }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error?.message ?? "Booking failed");
      return data as { public_id: string };
    },
    onSuccess: (b) => router.push(`/trips/${b.public_id}`),
    onError: (e) => {
      idemKey.current = crypto.randomUUID();
      toast.error(e instanceof Error ? e.message : errorMessage(e));
    },
  });

  return (
    <div className="space-y-3">
      <DateRangePicker
        value={range}
        onChange={setRange}
        disabled={(d) => blocked.has(isoDate(d)!)}
        placeholder="Check-in – check-out"
      />
      <div className="flex items-center gap-3">
        <Label htmlFor="bw-guests" className="shrink-0">
          Guests
        </Label>
        <Input
          id="bw-guests"
          type="number"
          min={1}
          max={listing.max_guests ?? 1}
          value={guests}
          onChange={(e) => setGuests(Math.max(1, Number(e.target.value)))}
        />
      </div>
      {ready && quote && (
        <div className="space-y-1 rounded-lg bg-muted/50 p-3 text-sm">
          {quote.available ? (
            <>
              <Row label={`${quote.nights} nights`} value={money(quote.subtotal, quote.currency)} />
              <Row label="Service fee" value={money(quote.service_fee, quote.currency)} />
              <div className="border-t pt-1 font-semibold">
                <Row label="Total" value={money(quote.total, quote.currency)} />
              </div>
            </>
          ) : (
            <p className="text-destructive">{quote.reason}</p>
          )}
        </div>
      )}
      {me && (
        <Button
          className="w-full"
          size="lg"
          disabled={!ready || !quote?.available || isFetching || reserve.isPending}
          onClick={() => reserve.mutate()}
        >
          Reserve
        </Button>
      )}
      {me && <p className="text-center text-xs text-muted-foreground">Dates are held for 30 minutes while you pay.</p>}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
