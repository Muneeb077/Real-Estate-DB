"use client";

import { useQuery } from "@tanstack/react-query";
import { PlusIcon } from "lucide-react";
import Link from "next/link";

import { PageTitle } from "@/components/auth/require-auth";
import { HostShell } from "@/components/host/host-shell";
import { ListingImage } from "@/components/listing/listing-image";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { MODE_LABEL, priceLabel, shortDate } from "@/lib/format";
import type { ListingMode, PriceUnit } from "@/lib/types";

type Row = {
  public_id: string;
  title: string;
  listing_mode: ListingMode;
  status: string;
  price: number;
  price_unit: PriceUnit;
  currency: string;
  city: string;
  moderation_note: string | null;
  updated_at: string;
  views: number;
  thumb: string | null;
};

export default function HostListingsPage() {
  const { data = [], isLoading } = useQuery({ queryKey: ["host-listings"], queryFn: () => api<Row[]>("/host/listings") });
  return (
    <HostShell>
      <PageTitle
        title="Your listings"
        action={
          <Button render={<Link href="/host/listings/new" />} nativeButton={false}>
            <PlusIcon /> New listing
          </Button>
        }
      />
      {isLoading ? (
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
      ) : (
        <ul className="divide-y rounded-xl border">
          {data.map((l) => (
            <li key={l.public_id}>
              <Link href={`/host/listings/${l.public_id}`} className="flex items-center gap-4 p-3 hover:bg-muted/50">
                <div className="relative size-16 shrink-0 overflow-hidden rounded-lg">
                  <ListingImage src={l.thumb} alt="" sizes="64px" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{l.title}</div>
                  <div className="text-sm text-muted-foreground">
                    {MODE_LABEL[l.listing_mode]} · {l.city} · {priceLabel(l.price, l.price_unit, l.currency)} · updated {shortDate(l.updated_at)}
                  </div>
                  {l.status === "rejected" && l.moderation_note && <div className="text-sm text-destructive">{l.moderation_note}</div>}
                </div>
                <div className="hidden text-sm text-muted-foreground sm:block">{l.views} views</div>
                <StatusBadge status={l.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </HostShell>
  );
}
