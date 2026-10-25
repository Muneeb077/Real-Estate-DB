"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCardIcon, LockIcon, MapPinIcon, PhoneIcon, StarIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { RequireAuth } from "@/components/auth/require-auth";
import { ListingImage } from "@/components/listing/listing-image";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { money, shortDate } from "@/lib/format";

type Booking = {
  public_id: string;
  check_in: string;
  check_out: string;
  nights: number;
  guests: number;
  subtotal: number;
  service_fee: number;
  total_price: number;
  currency: string;
  status: string;
  hold_expires_at: string | null;
  cancelled_by: string | null;
  refund_amount: number | null;
  listing_public_id: string;
  listing_title: string;
  listing_thumb: string | null;
  my_role: "guest" | "host";
  review: { rating: number; comment: string; host_reply: string | null } | null;
  address?: { street: string | null; city: string; postal_code: string | null; country: string };
  contact?: { name: string; phone: string | null };
};

export default function TripPage() {
  return <RequireAuth>{() => <Trip />}</RequireAuth>;
}

function Trip() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { data: b } = useQuery({ queryKey: ["booking", id], queryFn: () => api<Booking>(`/bookings/${id}`) });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["booking", id] });
    qc.invalidateQueries({ queryKey: ["my-bookings"] });
  };

  const pay = useMutation({
    mutationFn: () => api<{ status?: string; checkout_url?: string }>(`/bookings/${id}/pay`, { method: "POST" }),
    onSuccess: (r) => {
      if (r.checkout_url) window.location.href = r.checkout_url;
      else {
        toast.success("Payment received. Your stay is confirmed!");
        refresh();
      }
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const cancel = useMutation({
    mutationFn: () => api<{ refund_amount: number }>(`/bookings/${id}/cancel`, { method: "POST" }),
    onSuccess: (r) => {
      toast.success(r.refund_amount ? `Cancelled. ${money(r.refund_amount)} will be refunded.` : "Cancelled.");
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!b) return <div className="mx-auto h-96 max-w-4xl animate-pulse px-4 py-10" />;
  const canCancel = ["pending", "confirmed"].includes(b.status) && new Date(b.check_in) > new Date();

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <div className="flex flex-col gap-6 sm:flex-row">
        <div className="relative aspect-[4/3] w-full overflow-hidden rounded-xl sm:w-64">
          <ListingImage src={b.listing_thumb} alt={b.listing_title} sizes="256px" />
        </div>
        <div className="flex-1 space-y-2">
          <StatusBadge status={b.status} />
          <h1 className="text-2xl font-semibold">
            <Link href={`/listings/${b.listing_public_id}`} className="hover:underline">
              {b.listing_title}
            </Link>
          </h1>
          <p className="text-muted-foreground">
            {shortDate(b.check_in)} → {shortDate(b.check_out)} · {b.nights} nights · {b.guests} guests
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Price details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <Line label={`${b.nights} nights`} value={money(b.subtotal, b.currency)} />
            <Line label="Service fee" value={money(b.service_fee, b.currency)} />
            <div className="border-t pt-1 font-semibold">
              <Line label="Total" value={money(b.total_price, b.currency)} />
            </div>
            {b.refund_amount != null && b.status === "cancelled" && (
              <Line label={`Refund (cancelled by ${b.cancelled_by})`} value={money(b.refund_amount, b.currency)} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{b.status === "pending" ? "Complete your booking" : "Your stay"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {b.status === "pending" && b.my_role === "guest" && (
              <>
                <p className="text-muted-foreground">
                  Dates held until {b.hold_expires_at ? new Date(b.hold_expires_at).toLocaleTimeString() : "soon"}.
                  Demo payments are simulated unless Stripe test keys are configured.
                </p>
                <Button className="w-full" onClick={() => pay.mutate()} disabled={pay.isPending}>
                  <CreditCardIcon /> Pay {money(b.total_price, b.currency)}
                </Button>
              </>
            )}
            {b.address ? (
              <>
                <p className="flex items-start gap-2">
                  <MapPinIcon className="mt-0.5 size-4" />
                  {b.address.street}, {b.address.city} {b.address.postal_code}, {b.address.country}
                </p>
                <p className="flex items-center gap-2">
                  <PhoneIcon className="size-4" /> {b.contact?.name}: {b.contact?.phone ?? "no phone on file"}
                </p>
                <p className="flex items-center gap-1 text-xs text-muted-foreground">
                  <LockIcon className="size-3" /> Decrypted just for you because this booking is confirmed.
                </p>
              </>
            ) : (
              b.status !== "pending" && <p className="text-muted-foreground">Address details are hidden.</p>
            )}
            {canCancel && (
              <Button variant="outline" className="w-full" onClick={() => confirm("Cancel this booking?") && cancel.mutate()}>
                Cancel booking
              </Button>
            )}
            {canCancel && b.status === "confirmed" && b.my_role === "guest" && (
              <p className="text-xs text-muted-foreground">
                Free cancellation up to 7 days before check-in; after that 50% of the nightly price is refunded.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {b.my_role === "guest" && b.status === "completed" && <ReviewBox booking={b} onDone={refresh} />}
    </div>
  );
}

function ReviewBox({ booking, onDone }: { booking: Booking; onDone: () => void }) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const submit = useMutation({
    mutationFn: () => api(`/bookings/${booking.public_id}/review`, { body: { rating, comment } }),
    onSuccess: () => {
      toast.success("Thanks for your review!");
      onDone();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (booking.review) {
    return (
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Your review</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <Stars n={booking.review.rating} /> <p className="mt-2">{booking.review.comment}</p>
          {booking.review.host_reply && <p className="mt-2 border-l-2 pl-3">Host: {booking.review.host_reply}</p>}
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>How was your stay?</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-1" role="radiogroup" aria-label="Rating">
          {[1, 2, 3, 4, 5].map((n) => (
            <button key={n} role="radio" aria-checked={rating === n} aria-label={`${n} stars`} onClick={() => setRating(n)}>
              <StarIcon className={`size-6 ${n <= rating ? "fill-current text-amber-500" : "text-muted-foreground"}`} />
            </button>
          ))}
        </div>
        <Textarea rows={4} aria-label="Review" maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Tell future guests what you loved" />
        <Button onClick={() => submit.mutate()} disabled={comment.length < 10 || submit.isPending}>
          Post review
        </Button>
      </CardContent>
    </Card>
  );
}

function Stars({ n }: { n: number }) {
  return (
    <span className="inline-flex">
      {Array.from({ length: 5 }, (_, i) => (
        <StarIcon key={i} className={`size-4 ${i < n ? "fill-current text-amber-500" : "text-muted-foreground"}`} />
      ))}
    </span>
  );
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}
