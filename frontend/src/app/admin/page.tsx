"use client";

import { useQuery } from "@tanstack/react-query";

import { AdminShell } from "@/components/admin/admin-shell";
import { PageTitle } from "@/components/auth/require-auth";
import { SeriesBarChart, StatTile } from "@/components/charts/bar-chart";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

type Kpis = {
  totals: Record<string, number>;
  monthly: { month: string; kind: "sale" | "rental" | "stay"; gmv: number; platform_revenue: number; deals: number; gmv_growth_pct: number | null }[];
  top_hosts: { public_id: string; name: string; verification_status: string; deals: number; gmv: number; platform_revenue: number; share_pct: number; rnk: number }[];
  cities: { city: string; listings: number; median_nightly: number; avg_rating: number | null }[];
};

// Fixed identity per transaction kind (categorical slots 1-3, validated for both themes).
const KINDS = [
  { kind: "stay", label: "Stays", color: "var(--series-1)" },
  { kind: "rental", label: "Long-term rentals", color: "var(--series-2)" },
  { kind: "sale", label: "Sales", color: "var(--series-3)" },
] as const;

export default function AdminOverviewPage() {
  return (
    <AdminShell>
      <Overview />
    </AdminShell>
  );
}

function Overview() {
  const { data } = useQuery({ queryKey: ["admin-kpis"], queryFn: () => api<Kpis>("/admin/kpis") });
  if (!data) return <div className="h-96 animate-pulse rounded-xl bg-muted" />;
  const t = data.totals;
  const pct = (n: number) => `${n > 0 ? "+" : ""}${n}%`;
  return (
    <>
      <PageTitle title="Platform overview" description="Computed in MySQL with CTEs and window functions (AdminKpis, AdminMonthlyGmv, AdminTopHosts, AdminCityStats)." />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <StatTile label="GMV, 30 days" value={money(t.gmv_30d, "USD", true)} />
        <StatTile label="Platform revenue, 30 days" value={money(t.revenue_30d, "USD", true)} />
        <StatTile label="Active users" value={t.active_users.toLocaleString()} hint={`${t.new_users_30d} new in 30 days`} />
        <StatTile label="Live listings" value={t.published_listings.toLocaleString()} hint={`${t.hosts} hosts`} />
        <StatTile
          label="Needs attention"
          value={t.pending_review + t.pending_hosts + t.open_reports}
          hint={`${t.pending_review} listings · ${t.pending_hosts} hosts · ${t.open_reports} reports`}
        />
      </div>

      <h2 className="mt-10 mb-1 text-lg font-semibold">Gross merchandise value by month</h2>
      <p className="mb-4 text-sm text-muted-foreground">
        One chart per kind (sale values are ~100× stays, so a shared axis would flatten the others). Growth is LAG() over each
        kind&apos;s own series.
      </p>
      <div className="grid gap-4 lg:grid-cols-3">
        {KINDS.map((k) => (
          <SeriesBarChart
            key={k.kind}
            title={k.label}
            color={k.color}
            data={data.monthly.filter((m) => m.kind === k.kind).map((m) => ({ ...m, month: m.month.slice(2) }))}
            x="month"
            y="gmv"
            height={200}
            format={(n) => money(n, "USD", true)}
            extra={[
              { key: "deals", label: "Deals" },
              { key: "gmv_growth_pct", label: "MoM growth", format: pct },
              { key: "platform_revenue", label: "Platform revenue", format: (n) => money(n, "USD", true) },
            ]}
          />
        ))}
      </div>

      <div className="mt-10 grid gap-6 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-lg font-semibold">Top hosts, 12 months</h2>
          <div className="overflow-x-auto rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rank</TableHead>
                  <TableHead>Host</TableHead>
                  <TableHead className="text-right">Deals</TableHead>
                  <TableHead className="text-right">GMV</TableHead>
                  <TableHead className="text-right">Revenue share</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.top_hosts.map((h) => (
                  <TableRow key={h.public_id}>
                    <TableCell className="tabular-nums">{h.rnk}</TableCell>
                    <TableCell className="font-medium">{h.name}</TableCell>
                    <TableCell className="text-right tabular-nums">{h.deals.toLocaleString()}</TableCell>
                    <TableCell className="text-right tabular-nums">{money(h.gmv, "USD", true)}</TableCell>
                    <TableCell className="text-right tabular-nums">{h.share_pct}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
        <SeriesBarChart
          title="Median nightly price by city"
          subtitle="Median via ROW_NUMBER() and COUNT() windows: MySQL has no MEDIAN()"
          data={data.cities.slice(0, 12)}
          x="city"
          y="median_nightly"
          horizontal
          height={360}
          format={(n) => money(n)}
          extra={[
            { key: "listings", label: "Stays" },
            { key: "avg_rating", label: "Avg rating" },
          ]}
        />
      </div>
    </>
  );
}
