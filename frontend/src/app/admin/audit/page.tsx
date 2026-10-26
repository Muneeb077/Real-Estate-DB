"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AdminShell } from "@/components/admin/admin-shell";
import { PageTitle } from "@/components/auth/require-auth";
import { NativeSelect } from "@/components/search/filters-sheet";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";

type Entry = {
  id: number;
  action: string;
  entity: string;
  entity_id: number | null;
  old_data: Record<string, unknown> | null;
  new_data: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
  actor: string | null;
};

export default function AuditPage() {
  return (
    <AdminShell>
      <Audit />
    </AdminShell>
  );
}

function Audit() {
  const [entity, setEntity] = useState("");
  const q = useInfiniteQuery({
    queryKey: ["audit", entity],
    queryFn: ({ pageParam }) =>
      api<{ items: Entry[]; next_before: number | null }>(
        `/admin/audit?${new URLSearchParams({ ...(entity && { entity }), ...(pageParam && { before: String(pageParam) }) })}`,
      ),
    initialPageParam: 0,
    getNextPageParam: (p) => p.next_before ?? undefined,
  });
  const rows = q.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <>
      <PageTitle
        title="Audit log"
        description="Written by database triggers using the @actor_id session variable. Append-only: UPDATE and DELETE are rejected by triggers."
        action={
          <div className="w-44">
            <NativeSelect aria-label="Entity" value={entity} onChange={(e) => setEntity(e.target.value)}>
              <option value="">All entities</option>
              {["listing", "user", "host", "booking", "transaction", "review", "setting", "backup"].map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </NativeSelect>
          </div>
        }
      />
      <div className="overflow-x-auto rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When</TableHead>
              <TableHead>Actor</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Entity</TableHead>
              <TableHead>Change</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="text-xs whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</TableCell>
                <TableCell className="text-sm">{r.actor ?? <span className="text-muted-foreground">system</span>}</TableCell>
                <TableCell>
                  <code className="text-xs">{r.action}</code>
                </TableCell>
                <TableCell className="text-sm">
                  {r.entity}
                  {r.entity_id ? ` #${r.entity_id}` : ""}
                </TableCell>
                <TableCell className="max-w-md">
                  <code className="block truncate text-xs text-muted-foreground" title={JSON.stringify({ old: r.old_data, new: r.new_data })}>
                    {r.old_data ? `${JSON.stringify(r.old_data)} → ` : ""}
                    {JSON.stringify(r.new_data)}
                  </code>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {q.hasNextPage && (
        <Button variant="outline" className="mt-4" onClick={() => q.fetchNextPage()} disabled={q.isFetchingNextPage}>
          Load older entries
        </Button>
      )}
    </>
  );
}
