"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { money, shortDate } from "@/lib/format";

export type Offer = {
  public_id: string;
  amount: number;
  move_in_date: string | null;
  message: string | null;
  status: string;
  created_at: string;
  listing_id: string;
  listing_title: string;
  listing_mode: string;
  asking_price: number;
  currency: string;
  city: string;
  guest_name?: string;
};

export type Viewing = {
  public_id: string;
  scheduled_at: string;
  note: string | null;
  status: string;
  listing_id: string;
  listing_title: string;
  city: string;
  guest_name?: string;
};

export function OffersList() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({ queryKey: ["my-offers"], queryFn: () => api<Offer[]>("/me/offers") });
  const withdraw = useMutation({
    mutationFn: (id: string) => api(`/offers/${id}/withdraw`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-offers"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (isLoading) return <div className="h-32 animate-pulse rounded-xl bg-muted" />;
  if (!data.length) return <Empty text="No offers or rental applications yet." />;
  return (
    <ul className="divide-y rounded-xl border">
      {data.map((o) => (
        <li key={o.public_id} className="flex flex-wrap items-center gap-4 p-4">
          <div className="min-w-0 flex-1">
            <Link href={`/listings/${o.listing_id}`} className="font-medium hover:underline">
              {o.listing_title}
            </Link>
            <div className="text-sm text-muted-foreground">
              {o.city} · {o.listing_mode === "sale" ? "Offer" : "Application"} of {money(o.amount, o.currency)}
              {o.listing_mode === "sale" ? "" : "/month"} (asking {money(o.asking_price, o.currency)}) ·{" "}
              {shortDate(o.created_at)}
            </div>
          </div>
          <StatusBadge status={o.status} />
          {o.status === "pending" && (
            <Button variant="outline" size="sm" onClick={() => withdraw.mutate(o.public_id)}>
              Withdraw
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}

export function ViewingsList() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({ queryKey: ["my-viewings"], queryFn: () => api<Viewing[]>("/me/viewings") });
  const cancel = useMutation({
    mutationFn: (id: string) => api(`/viewings/${id}`, { method: "PATCH", body: { status: "cancelled" } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-viewings"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (isLoading) return <div className="h-32 animate-pulse rounded-xl bg-muted" />;
  if (!data.length) return <Empty text="No viewings booked." />;
  return (
    <ul className="divide-y rounded-xl border">
      {data.map((v) => (
        <li key={v.public_id} className="flex flex-wrap items-center gap-4 p-4">
          <div className="min-w-0 flex-1">
            <Link href={`/listings/${v.listing_id}`} className="font-medium hover:underline">
              {v.listing_title}
            </Link>
            <div className="text-sm text-muted-foreground">
              {v.city} · {new Date(v.scheduled_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
            </div>
          </div>
          <StatusBadge status={v.status} />
          {["requested", "confirmed"].includes(v.status) && (
            <Button variant="outline" size="sm" onClick={() => cancel.mutate(v.public_id)}>
              Cancel
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}

export function Empty({ text }: { text: string }) {
  return <p className="rounded-xl border border-dashed py-12 text-center text-muted-foreground">{text}</p>;
}
