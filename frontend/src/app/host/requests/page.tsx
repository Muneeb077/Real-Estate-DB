"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { toast } from "sonner";

import { PageTitle } from "@/components/auth/require-auth";
import { HostShell } from "@/components/host/host-shell";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, errorMessage } from "@/lib/api";
import { money, shortDate } from "@/lib/format";

import { Empty, type Offer, type Viewing } from "../../trips/lists";

export default function HostRequestsPage() {
  return (
    <HostShell>
      <PageTitle title="Offers & viewings" description="Accepting an offer closes the listing and records the sale in one transaction." />
      <Tabs defaultValue="offers">
        <TabsList>
          <TabsTrigger value="offers">Offers & applications</TabsTrigger>
          <TabsTrigger value="viewings">Viewings</TabsTrigger>
        </TabsList>
        <TabsContent value="offers" className="pt-4">
          <Offers />
        </TabsContent>
        <TabsContent value="viewings" className="pt-4">
          <Viewings />
        </TabsContent>
      </Tabs>
    </HostShell>
  );
}

function Offers() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({ queryKey: ["host-offers"], queryFn: () => api<Offer[]>("/host/offers") });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "accept" | "decline" }) => api(`/offers/${id}/${action}`, { method: "POST" }),
    onSuccess: (_, { action }) => {
      toast.success(action === "accept" ? "Offer accepted: the listing is closed and the transaction recorded." : "Offer declined");
      qc.invalidateQueries({ queryKey: ["host-offers"] });
      qc.invalidateQueries({ queryKey: ["host-dashboard"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (isLoading) return <div className="h-32 animate-pulse rounded-xl bg-muted" />;
  if (!data.length) return <Empty text="No offers yet." />;
  return (
    <ul className="divide-y rounded-xl border">
      {data.map((o) => (
        <li key={o.public_id} className="flex flex-wrap items-center gap-4 p-4">
          <div className="min-w-0 flex-1">
            <div className="font-medium">
              {o.guest_name} offered {money(o.amount, o.currency)}
              {o.listing_mode === "sale" ? "" : "/month"}
              <span className="font-normal text-muted-foreground"> (asking {money(o.asking_price, o.currency)})</span>
            </div>
            <Link href={`/listings/${o.listing_id}`} className="text-sm text-muted-foreground hover:underline">
              {o.listing_title}
            </Link>
            {o.move_in_date && <div className="text-sm text-muted-foreground">Move-in {shortDate(o.move_in_date)}</div>}
            {o.message && <p className="mt-1 text-sm">“{o.message}”</p>}
          </div>
          <StatusBadge status={o.status} />
          {o.status === "pending" && (
            <div className="flex gap-2">
              <Button size="sm" onClick={() => confirm("Accept this offer? Other pending offers will be closed.") && act.mutate({ id: o.public_id, action: "accept" })}>
                Accept
              </Button>
              <Button size="sm" variant="outline" onClick={() => act.mutate({ id: o.public_id, action: "decline" })}>
                Decline
              </Button>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

function Viewings() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useQuery({ queryKey: ["host-viewings"], queryFn: () => api<Viewing[]>("/host/viewings") });
  const act = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api(`/viewings/${id}`, { method: "PATCH", body: { status } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["host-viewings"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (isLoading) return <div className="h-32 animate-pulse rounded-xl bg-muted" />;
  if (!data.length) return <Empty text="No viewing requests." />;
  return (
    <ul className="divide-y rounded-xl border">
      {data.map((v) => (
        <li key={v.public_id} className="flex flex-wrap items-center gap-4 p-4">
          <div className="min-w-0 flex-1">
            <div className="font-medium">
              {v.guest_name} · {new Date(v.scheduled_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
            </div>
            <div className="text-sm text-muted-foreground">{v.listing_title}</div>
            {v.note && <p className="mt-1 text-sm">“{v.note}”</p>}
          </div>
          <StatusBadge status={v.status} />
          {v.status === "requested" && (
            <div className="flex gap-2">
              <Button size="sm" onClick={() => act.mutate({ id: v.public_id, status: "confirmed" })}>
                Confirm
              </Button>
              <Button size="sm" variant="outline" onClick={() => act.mutate({ id: v.public_id, status: "declined" })}>
                Decline
              </Button>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
