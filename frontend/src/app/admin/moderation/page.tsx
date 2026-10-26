"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOffIcon, StarIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AdminShell } from "@/components/admin/admin-shell";
import { PageTitle } from "@/components/auth/require-auth";
import { ListingImage } from "@/components/listing/listing-image";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Empty } from "@/app/trips/lists";
import { api, errorMessage } from "@/lib/api";
import { MODE_LABEL, priceLabel, shortDate } from "@/lib/format";
import type { ListingMode, PriceUnit } from "@/lib/types";

export default function ModerationPage() {
  return (
    <AdminShell>
      <PageTitle title="Moderation" description="Listings awaiting review, host verification, user reports and review moderation." />
      <Tabs defaultValue="listings">
        <TabsList>
          <TabsTrigger value="listings">Listings</TabsTrigger>
          <TabsTrigger value="hosts">Host verification</TabsTrigger>
          <TabsTrigger value="reports">Reports</TabsTrigger>
          <TabsTrigger value="reviews">Reviews</TabsTrigger>
        </TabsList>
        <TabsContent value="listings" className="pt-4">
          <ListingQueue />
        </TabsContent>
        <TabsContent value="hosts" className="pt-4">
          <HostQueue />
        </TabsContent>
        <TabsContent value="reports" className="pt-4">
          <Reports />
        </TabsContent>
        <TabsContent value="reviews" className="pt-4">
          <Reviews />
        </TabsContent>
      </Tabs>
    </AdminShell>
  );
}

function useAction<T>(key: string, fn: (v: T) => Promise<unknown>, ok: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      toast.success(ok);
      qc.invalidateQueries({ queryKey: [key] });
      qc.invalidateQueries({ queryKey: ["admin-kpis"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

type QueueItem = {
  public_id: string;
  title: string;
  description: string;
  listing_mode: ListingMode;
  price: number;
  price_unit: PriceUnit;
  currency: string;
  city: string;
  host_name: string;
  host_verification: string;
  photos: number;
  thumb: string | null;
  updated_at: string;
};

function ListingQueue() {
  const { data = [], isLoading } = useQuery({ queryKey: ["mod-listings"], queryFn: () => api<QueueItem[]>("/admin/listings") });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const act = useAction(
    "mod-listings",
    ({ id, decision }: { id: string; decision: string }) =>
      api(`/admin/listings/${id}/moderate`, { body: { decision, note: notes[id] || null } }),
    "Decision saved",
  );
  if (isLoading) return <div className="h-40 animate-pulse rounded-xl bg-muted" />;
  if (!data.length) return <Empty text="No listings waiting for review." />;
  return (
    <ul className="space-y-3">
      {data.map((l) => (
        <li key={l.public_id} className="flex flex-col gap-4 rounded-xl border p-4 sm:flex-row">
          <div className="relative aspect-[4/3] w-full shrink-0 overflow-hidden rounded-lg sm:w-48">
            <ListingImage src={l.thumb} alt="" sizes="192px" />
          </div>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="font-semibold">{l.title}</div>
            <div className="text-sm text-muted-foreground">
              {MODE_LABEL[l.listing_mode]} · {l.city} · {priceLabel(l.price, l.price_unit, l.currency)} · {l.photos} photos · by {l.host_name}{" "}
              <StatusBadge status={l.host_verification} />
            </div>
            <p className="line-clamp-3 text-sm">{l.description}</p>
            <div className="flex flex-wrap gap-2 pt-2">
              <Button size="sm" onClick={() => act.mutate({ id: l.public_id, decision: "approve" })}>
                Approve & publish
              </Button>
              <Input
                className="h-7 w-64"
                placeholder="Reason (required to reject)"
                value={notes[l.public_id] ?? ""}
                onChange={(e) => setNotes({ ...notes, [l.public_id]: e.target.value })}
              />
              <Button size="sm" variant="outline" onClick={() => act.mutate({ id: l.public_id, decision: "reject" })}>
                Reject
              </Button>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

type HostItem = { public_id: string; name: string; agency_name: string | null; license_number: string | null; listings: number; created_at: string };

function HostQueue() {
  const { data = [], isLoading } = useQuery({ queryKey: ["mod-hosts"], queryFn: () => api<HostItem[]>("/admin/hosts") });
  const act = useAction(
    "mod-hosts",
    ({ id, decision }: { id: string; decision: string }) => api(`/admin/hosts/${id}/verify`, { body: { decision } }),
    "Host updated",
  );
  if (isLoading) return <div className="h-40 animate-pulse rounded-xl bg-muted" />;
  if (!data.length) return <Empty text="No hosts waiting for verification." />;
  return (
    <ul className="divide-y rounded-xl border">
      {data.map((h) => (
        <li key={h.public_id} className="flex flex-wrap items-center gap-4 p-4">
          <div className="flex-1">
            <Link href={`/hosts/${h.public_id}`} className="font-medium hover:underline">
              {h.name}
            </Link>
            <div className="text-sm text-muted-foreground">
              {h.agency_name ?? "Independent"} · license <code>{h.license_number ?? "none"}</code> (decrypted, view audited) · applied{" "}
              {shortDate(h.created_at)}
            </div>
          </div>
          <Button size="sm" onClick={() => act.mutate({ id: h.public_id, decision: "verified" })}>
            Verify
          </Button>
          <Button size="sm" variant="outline" onClick={() => act.mutate({ id: h.public_id, decision: "rejected" })}>
            Reject
          </Button>
        </li>
      ))}
    </ul>
  );
}

type ReportItem = {
  id: number;
  entity: string;
  reason: string;
  details: string | null;
  reporter: string;
  target_public_id: string;
  target_name: string;
  reports_on_target: number;
  created_at: string;
};

function Reports() {
  const { data = [], isLoading } = useQuery({ queryKey: ["mod-reports"], queryFn: () => api<ReportItem[]>("/admin/reports") });
  const act = useAction(
    "mod-reports",
    ({ id, status, hide }: { id: number; status: string; hide?: boolean }) =>
      api(`/admin/reports/${id}`, { body: { status, hide_listing: !!hide } }),
    "Report resolved",
  );
  if (isLoading) return <div className="h-40 animate-pulse rounded-xl bg-muted" />;
  if (!data.length) return <Empty text="No open reports." />;
  return (
    <ul className="divide-y rounded-xl border">
      {data.map((r) => (
        <li key={r.id} className="flex flex-wrap items-center gap-4 p-4">
          <div className="flex-1">
            <div className="font-medium">
              {r.entity === "listing" ? (
                <Link href={`/listings/${r.target_public_id}`} className="hover:underline">
                  {r.target_name}
                </Link>
              ) : (
                r.target_name
              )}{" "}
              <span className="text-sm font-normal text-muted-foreground">
                · {r.reason} · {r.reports_on_target} report{r.reports_on_target > 1 ? "s" : ""}
              </span>
            </div>
            <div className="text-sm text-muted-foreground">
              by {r.reporter} on {shortDate(r.created_at)}
              {r.details ? `: “${r.details}”` : ""}
            </div>
          </div>
          {r.entity === "listing" && (
            <Button size="sm" variant="destructive" onClick={() => act.mutate({ id: r.id, status: "actioned", hide: true })}>
              <EyeOffIcon /> Pause listing
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={() => act.mutate({ id: r.id, status: "dismissed" })}>
            Dismiss
          </Button>
        </li>
      ))}
    </ul>
  );
}

type ReviewItem = { id: number; rating: number; comment: string; hidden: number; listing_id: string; listing_title: string; author: string; created_at: string };

function Reviews() {
  const { data = [] } = useQuery({ queryKey: ["mod-reviews"], queryFn: () => api<ReviewItem[]>("/admin/reviews") });
  const act = useAction(
    "mod-reviews",
    ({ id, hidden }: { id: number; hidden: boolean }) => api(`/admin/reviews/${id}`, { method: "PATCH", body: { hidden } }),
    "Review updated; the listing rating was recalculated by a trigger",
  );
  return (
    <ul className="divide-y rounded-xl border">
      {data.map((r) => (
        <li key={r.id} className="flex flex-wrap items-center gap-4 p-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 text-sm">
              <span className="flex items-center gap-0.5 font-medium">
                <StarIcon className="size-3.5 fill-current" /> {r.rating}
              </span>
              <span className="text-muted-foreground">
                {r.author} on <Link href={`/listings/${r.listing_id}`} className="hover:underline">{r.listing_title}</Link>
              </span>
            </div>
            <p className="text-sm">{r.comment}</p>
          </div>
          <Button size="sm" variant="outline" onClick={() => act.mutate({ id: r.id, hidden: !r.hidden })}>
            {r.hidden ? "Unhide" : "Hide"}
          </Button>
        </li>
      ))}
    </ul>
  );
}
