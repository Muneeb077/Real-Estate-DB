"use client";

import { useQuery } from "@tanstack/react-query";
import { PlusIcon, ShieldAlertIcon } from "lucide-react";
import Link from "next/link";

import { PageTitle } from "@/components/auth/require-auth";
import { SeriesBarChart, StatTile } from "@/components/charts/bar-chart";
import { HostShell } from "@/components/host/host-shell";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { money, priceLabel, shortDate } from "@/lib/format";
import type { PriceUnit } from "@/lib/types";

type Dashboard = {
  summary: {
    published: number;
    in_progress: number;
    upcoming_stays: number;
    pending_offers: number;
    pending_viewings: number;
    rating_avg: number | null;
    payout_this_month: number;
    verification: string;
  };
  earnings: { month: string; gross: number; commission: number; payout: number; deals: number; running_payout: number }[];
  listings: {
    public_id: string;
    title: string;
    listing_mode: string;
    status: string;
    price: number;
    price_unit: PriceUnit;
    views: number;
    favorites: number;
    bookings_90d: number;
    occupancy_pct: number | null;
    conversion_pct: number | null;
    payout_12m: number;
    revenue_rank: number;
    rating_avg: number | null;
  }[];
  upcoming: { public_id: string; check_in: string; check_out: string; guests: number; total_price: number; currency: string; listing_title: string; guest_name: string }[];
};

export default function HostDashboardPage() {
  return (
    <HostShell>
      <Dashboard />
    </HostShell>
  );
}

function Dashboard() {
  const { data } = useQuery({ queryKey: ["host-dashboard"], queryFn: () => api<Dashboard>("/host/dashboard") });
  if (!data) return <div className="h-96 animate-pulse rounded-xl bg-muted" />;
  const s = data.summary;
  const year = data.earnings.at(-1)?.running_payout ?? 0;
  return (
    <>
      <PageTitle
        title="Host dashboard"
        action={
          <Button render={<Link href="/host/listings/new" />} nativeButton={false}>
            <PlusIcon /> New listing
          </Button>
        }
      />
      {s.verification !== "verified" && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          <ShieldAlertIcon className="size-4" /> Verification: <StatusBadge status={s.verification} />
          An admin reviews your license before the verified badge appears on your listings.
        </div>
      )}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatTile label="Payout this month" value={money(s.payout_this_month)} />
        <StatTile label="Payout, 12 months" value={money(year)} />
        <StatTile label="Live listings" value={s.published} hint={`${s.in_progress} in progress`} />
        <StatTile label="Upcoming stays" value={s.upcoming_stays} />
        <StatTile
          label="Open requests"
          value={s.pending_offers + s.pending_viewings}
          hint={<Link href="/host/requests" className="underline">{s.pending_offers} offers · {s.pending_viewings} viewings</Link>}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[2fr_1fr]">
        <SeriesBarChart
          title="Monthly payout"
          subtitle="After refunds, service fees and platform commission (HostEarnings procedure)"
          data={data.earnings}
          x="month"
          y="payout"
          format={(n) => money(n, "USD", true)}
          extra={[
            { key: "deals", label: "Deals" },
            { key: "running_payout", label: "Running total", format: (n) => money(n, "USD", true) },
          ]}
        />
        <div className="rounded-xl border bg-card p-4">
          <div className="mb-3 font-medium">Upcoming stays</div>
          {data.upcoming.length ? (
            <ul className="space-y-3 text-sm">
              {data.upcoming.map((b) => (
                <li key={b.public_id}>
                  <Link href={`/trips/${b.public_id}`} className="block hover:underline">
                    <div className="font-medium">{b.guest_name}</div>
                    <div className="truncate text-muted-foreground">{b.listing_title}</div>
                    <div className="text-muted-foreground">
                      {shortDate(b.check_in)} → {shortDate(b.check_out)} · {money(b.total_price, b.currency)}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No upcoming stays.</p>
          )}
        </div>
      </div>

      <h2 className="mt-10 mb-3 text-lg font-semibold">Listing performance</h2>
      <div className="overflow-x-auto rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>Listing</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Price</TableHead>
              <TableHead className="text-right">Views</TableHead>
              <TableHead className="text-right">Saves</TableHead>
              <TableHead className="text-right">Bookings 90d</TableHead>
              <TableHead className="text-right">Occupancy</TableHead>
              <TableHead className="text-right">Payout 12m</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.listings.map((l) => (
              <TableRow key={l.public_id}>
                <TableCell className="text-muted-foreground tabular-nums">{l.revenue_rank}</TableCell>
                <TableCell className="max-w-64 truncate">
                  <Link href={`/host/listings/${l.public_id}`} className="font-medium hover:underline">
                    {l.title}
                  </Link>
                </TableCell>
                <TableCell>
                  <StatusBadge status={l.status} />
                </TableCell>
                <TableCell className="text-right tabular-nums">{priceLabel(l.price, l.price_unit, "USD", true)}</TableCell>
                <TableCell className="text-right tabular-nums">{l.views}</TableCell>
                <TableCell className="text-right tabular-nums">{l.favorites}</TableCell>
                <TableCell className="text-right tabular-nums">{l.bookings_90d}</TableCell>
                <TableCell className="text-right tabular-nums">{l.occupancy_pct == null ? "–" : `${l.occupancy_pct}%`}</TableCell>
                <TableCell className="text-right tabular-nums">{money(l.payout_12m, "USD", true)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
