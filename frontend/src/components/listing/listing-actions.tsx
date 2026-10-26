"use client";

import { useMutation } from "@tanstack/react-query";
import { CalendarClockIcon, FlagIcon, HandCoinsIcon, MessageSquareIcon, PencilIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/auth/field";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { priceLabel } from "@/lib/format";
import type { ListingDetail } from "@/lib/types";

import { BookingWidget } from "./booking-widget";

type DialogKind = "message" | "viewing" | "offer" | "report" | null;

/**
 * Sticky action panel on the listing page. Browsing is public; acting needs an
 * account, and contacting a host needs a verified email (enforced by the API).
 */
export function ListingActions({ listing }: { listing: ListingDetail }) {
  const { data: me } = useMe();
  const [open, setOpen] = useState<DialogKind>(null);
  const isStay = listing.listing_mode === "short_term_stay";
  const isOwner = me?.public_id === listing.host.public_id;
  const loginHref = `/login?next=/listings/${listing.public_id}`;

  return (
    <>
      <Card className="shadow-lg">
        <CardContent className="space-y-4">
          <div className="text-2xl font-semibold">{priceLabel(listing.price, listing.price_unit, listing.currency)}</div>
          {isOwner ? (
            <Button className="w-full" variant="outline" render={<Link href={`/host/listings/${listing.public_id}`} />} nativeButton={false}>
              <PencilIcon /> This is your listing. Edit it.
            </Button>
          ) : !me ? (
            <>
              {isStay && <BookingWidget listing={listing} />}
              <Button className="w-full" size="lg" render={<Link href={loginHref} />} nativeButton={false}>
                Log in to {isStay ? "book" : "make an offer"}
              </Button>
            </>
          ) : isStay ? (
            <BookingWidget listing={listing} />
          ) : (
            <div className="grid gap-2">
              <Button size="lg" onClick={() => setOpen("offer")}>
                <HandCoinsIcon /> {listing.listing_mode === "sale" ? "Make an offer" : "Apply to rent"}
              </Button>
              <Button variant="outline" onClick={() => setOpen("viewing")}>
                <CalendarClockIcon /> Request a viewing
              </Button>
            </div>
          )}
          {me && !isOwner && (
            <Button variant="ghost" className="w-full" onClick={() => setOpen("message")}>
              <MessageSquareIcon /> Message the host
            </Button>
          )}
        </CardContent>
      </Card>
      {me && !isOwner && (
        <button className="mx-auto mt-3 flex items-center gap-1 text-xs text-muted-foreground underline" onClick={() => setOpen("report")}>
          <FlagIcon className="size-3" /> Report this listing
        </button>
      )}
      <MessageDialog listing={listing} open={open === "message"} onClose={() => setOpen(null)} />
      <ViewingDialog listing={listing} open={open === "viewing"} onClose={() => setOpen(null)} />
      <OfferDialog listing={listing} open={open === "offer"} onClose={() => setOpen(null)} />
      <ReportDialog listing={listing} open={open === "report"} onClose={() => setOpen(null)} />
    </>
  );
}

type DialogProps = { listing: ListingDetail; open: boolean; onClose: () => void };

function MessageDialog({ listing, open, onClose }: DialogProps) {
  const router = useRouter();
  const [text, setText] = useState("");
  const send = useMutation({
    mutationFn: () =>
      api<{ conversation: string }>(`/listings/${listing.public_id}/conversations`, { body: { message: text } }),
    onSuccess: (r) => router.push(`/inbox/${r.conversation}`),
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Message {listing.host.name}</DialogTitle>
          <DialogDescription>Messages are encrypted at rest. Don&apos;t share payment details in chat.</DialogDescription>
        </DialogHeader>
        <Textarea rows={5} aria-label="Message" value={text} maxLength={4000} onChange={(e) => setText(e.target.value)} placeholder="Hi! Is the place still available?" />
        <DialogFooter>
          <Button onClick={() => send.mutate()} disabled={!text.trim() || send.isPending}>
            Send
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ViewingDialog({ listing, open, onClose }: DialogProps) {
  const [when, setWhen] = useState("");
  const [note, setNote] = useState("");
  const request = useMutation({
    mutationFn: () => api(`/listings/${listing.public_id}/viewings`, { body: { scheduled_at: when, note: note || null } }),
    onSuccess: () => {
      toast.success("Viewing requested. The host will confirm.");
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Request a viewing</DialogTitle>
          <DialogDescription>Pick a time at least 2 hours from now.</DialogDescription>
        </DialogHeader>
        <Field label="Date and time" type="datetime-local" name="when" value={when} onChange={(e) => setWhen(e.target.value)} />
        <div className="space-y-1.5">
          <Label htmlFor="viewing-note">Note (optional)</Label>
          <Textarea id="viewing-note" rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        <DialogFooter>
          <Button onClick={() => request.mutate()} disabled={!when || request.isPending}>
            Request viewing
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function OfferDialog({ listing, open, onClose }: DialogProps) {
  const router = useRouter();
  const isSale = listing.listing_mode === "sale";
  const [amount, setAmount] = useState(String(listing.price));
  const [moveIn, setMoveIn] = useState("");
  const [message, setMessage] = useState("");
  const submit = useMutation({
    mutationFn: () =>
      api(`/listings/${listing.public_id}/offers`, {
        body: { amount: Number(amount), move_in_date: moveIn || null, message: message || null },
      }),
    onSuccess: () => {
      toast.success(isSale ? "Offer sent" : "Application sent");
      router.push("/trips");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isSale ? "Make an offer" : "Apply to rent"}</DialogTitle>
          <DialogDescription>
            Asking {priceLabel(listing.price, listing.price_unit, listing.currency)}. When the host accepts, the sale
            is recorded in one database transaction and other offers are closed.
          </DialogDescription>
        </DialogHeader>
        <Field
          label={isSale ? `Your offer (${listing.currency})` : `Monthly rent you offer (${listing.currency})`}
          type="number"
          name="amount"
          min={1}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        {!isSale && <Field label="Move-in date" type="date" name="move_in" value={moveIn} onChange={(e) => setMoveIn(e.target.value)} />}
        <div className="space-y-1.5">
          <Label htmlFor="offer-msg">Message to the host (optional)</Label>
          <Textarea id="offer-msg" rows={3} maxLength={1000} value={message} onChange={(e) => setMessage(e.target.value)} />
        </div>
        <DialogFooter>
          <Button onClick={() => submit.mutate()} disabled={!Number(amount) || submit.isPending}>
            Send {isSale ? "offer" : "application"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ReportDialog({ listing, open, onClose }: DialogProps) {
  const [reason, setReason] = useState("inaccurate");
  const [details, setDetails] = useState("");
  const send = useMutation({
    mutationFn: () => api("/reports", { body: { entity: "listing", public_id: listing.public_id, reason, details: details || null } }),
    onSuccess: () => {
      toast.success("Thanks. Our team will review it.");
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Report this listing</DialogTitle>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="report-reason">Reason</Label>
          <select
            id="report-reason"
            className="h-9 w-full rounded-lg border bg-background px-2.5 text-sm"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          >
            <option value="inaccurate">Inaccurate or misleading</option>
            <option value="scam">Looks like a scam</option>
            <option value="spam">Spam</option>
            <option value="offensive">Offensive</option>
            <option value="other">Something else</option>
          </select>
        </div>
        <Textarea aria-label="Details" rows={3} maxLength={1000} value={details} onChange={(e) => setDetails(e.target.value)} placeholder="Details (optional)" />
        <DialogFooter>
          <Button onClick={() => send.mutate()} disabled={send.isPending}>
            Submit report
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
