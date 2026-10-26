"use client";

import { TableIcon, BarChart3Icon } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Button } from "@/components/ui/button";

type Row = Record<string, string | number | null>;

const compact = (n: number) => new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);

/**
 * Single-series bar chart: one hue (the series colour token), 24px max bar width,
 * 4px rounded data-end, hairline recessive grid, hover tooltip, and a table view
 * (identity and values never depend on colour alone).
 */
export function SeriesBarChart({
  data,
  x,
  y,
  title,
  subtitle,
  color = "var(--series-1)",
  format = (n) => compact(n),
  horizontal = false,
  height = 240,
  extra,
}: {
  data: Row[];
  x: string;
  y: string;
  title: string;
  subtitle?: string;
  color?: string;
  format?: (n: number) => string;
  horizontal?: boolean;
  height?: number;
  extra?: { key: string; label: string; format?: (v: number) => string }[];
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <figure className="rounded-xl border bg-card p-4">
      <figcaption className="mb-3 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 font-medium">
            <span className="size-2.5 rounded-sm" style={{ background: color }} aria-hidden />
            {title}
          </div>
          {subtitle && <div className="text-xs text-muted-foreground">{subtitle}</div>}
        </div>
        <Button variant="ghost" size="icon-sm" aria-label={asTable ? "Show chart" : "Show table"} onClick={() => setAsTable(!asTable)}>
          {asTable ? <BarChart3Icon /> : <TableIcon />}
        </Button>
      </figcaption>
      {asTable ? (
        <div className="max-h-[260px] overflow-auto text-sm">
          <table className="w-full">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1 font-medium">{x}</th>
                <th className="py-1 text-right font-medium">{title}</th>
                {extra?.map((e) => (
                  <th key={e.key} className="py-1 text-right font-medium">
                    {e.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={String(r[x])} className="border-t">
                  <td className="py-1">{r[x]}</td>
                  <td className="py-1 text-right tabular-nums">{format(Number(r[y] ?? 0))}</td>
                  {extra?.map((e) => (
                    <td key={e.key} className="py-1 text-right tabular-nums">
                      {r[e.key] == null ? "–" : e.format ? e.format(Number(r[e.key])) : r[e.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} barCategoryGap={2}>
            <CartesianGrid stroke="var(--chart-grid)" strokeWidth={1} horizontal={!horizontal} vertical={horizontal} />
            {horizontal ? (
              <>
                <XAxis type="number" tickFormatter={format} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey={x} width={96} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} axisLine={false} tickLine={false} />
              </>
            ) : (
              <>
                <XAxis dataKey={x} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={format} width={48} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} axisLine={false} tickLine={false} />
              </>
            )}
            <Tooltip
              cursor={{ fill: "var(--muted)", opacity: 0.6 }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <div className="rounded-md border bg-popover px-3 py-2 text-xs shadow-md">
                    <div className="font-medium">{label}</div>
                    <div className="flex items-center gap-1.5">
                      <span className="size-2 rounded-sm" style={{ background: color }} />
                      {title}: {format(Number(payload[0].value))}
                    </div>
                    {extra?.map((e) => {
                      const v = (payload[0].payload as Row)[e.key];
                      return (
                        <div key={e.key} className="text-muted-foreground">
                          {e.label}: {v == null ? "–" : e.format ? e.format(Number(v)) : v}
                        </div>
                      );
                    })}
                  </div>
                ) : null
              }
            />
            <Bar dataKey={y} fill={color} maxBarSize={24} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </figure>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}
