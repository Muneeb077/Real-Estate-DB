"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseBackupIcon, DownloadIcon, LockIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AdminShell } from "@/components/admin/admin-shell";
import { Field } from "@/components/auth/field";
import { PageTitle } from "@/components/auth/require-auth";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, errorMessage } from "@/lib/api";

type Settings = { service_fee_rate: number; default_commission_rate: number; booking_hold_minutes: number; new_listings_require_review: boolean };
type Backup = { id: number; file_name: string | null; size_bytes: number | null; sha256: string | null; kek_id: string | null; status: string; error: string | null; created_at: string; created_by: string | null };

export default function AdminSettingsPage() {
  return (
    <AdminShell>
      <PageTitle title="Settings & backups" />
      <div className="grid gap-6 lg:grid-cols-2">
        <PlatformSettings />
        <Backups />
      </div>
    </AdminShell>
  );
}

function PlatformSettings() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["admin-settings"], queryFn: () => api<Settings>("/admin/settings") });
  const [s, setS] = useState<Settings | null>(null);
  useEffect(() => {
    if (data) setS(data);
  }, [data]);
  const save = useMutation({
    mutationFn: () => api<Settings>("/admin/settings", { method: "PATCH", body: s }),
    onSuccess: (d) => {
      qc.setQueryData(["admin-settings"], d);
      toast.success("Settings saved (audited)");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!s) return <div className="h-64 animate-pulse rounded-xl bg-muted" />;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Platform settings</CardTitle>
        <CardDescription>Read by the stored procedures at booking and sale time.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Field label="Guest service fee (0–0.3)" name="fee" type="number" step="0.01" value={s.service_fee_rate} onChange={(e) => setS({ ...s, service_fee_rate: Number(e.target.value) })} />
        <Field label="Default host commission (0–0.2)" name="commission" type="number" step="0.005" value={s.default_commission_rate} onChange={(e) => setS({ ...s, default_commission_rate: Number(e.target.value) })} />
        <Field label="Booking hold (minutes)" name="hold" type="number" value={s.booking_hold_minutes} onChange={(e) => setS({ ...s, booking_hold_minutes: Number(e.target.value) })} />
        <label className="flex items-center gap-3 text-sm">
          <Switch checked={s.new_listings_require_review} onCheckedChange={(c) => setS({ ...s, new_listings_require_review: c })} />
          New listings require admin review
        </label>
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          Save settings
        </Button>
      </CardContent>
    </Card>
  );
}

function Backups() {
  const qc = useQueryClient();
  const { data = [] } = useQuery({
    queryKey: ["admin-backups"],
    queryFn: () => api<Backup[]>("/admin/backups"),
    refetchInterval: (q) => (q.state.data?.some((b) => b.status === "running") ? 2000 : false),
  });
  const start = useMutation({
    mutationFn: () => api("/admin/backups", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-backups"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <LockIcon className="size-4" /> Encrypted backups
        </CardTitle>
        <CardDescription>
          mysqldump runs as a read-only account and streams through chunked AES-256-GCM. Plaintext never touches disk. Restore
          with <code>scripts/decrypt_backup.py</code> and the KEK.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={() => start.mutate()} disabled={start.isPending || data.some((b) => b.status === "running")}>
          <DatabaseBackupIcon /> Back up now
        </Button>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>When</TableHead>
              <TableHead>Size</TableHead>
              <TableHead>Status</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((b) => (
              <TableRow key={b.id}>
                <TableCell className="text-xs">
                  {new Date(b.created_at).toLocaleString()}
                  {b.sha256 && <div className="font-mono text-muted-foreground" title={b.sha256}>sha256 {b.sha256.slice(0, 12)}… · KEK {b.kek_id}</div>}
                  {b.error && <div className="text-destructive">{b.error}</div>}
                </TableCell>
                <TableCell className="text-sm tabular-nums">{b.size_bytes ? `${(b.size_bytes / 1e6).toFixed(1)} MB` : "–"}</TableCell>
                <TableCell>
                  <StatusBadge status={b.status} />
                </TableCell>
                <TableCell>
                  {b.status === "succeeded" && (
                    <Button size="icon-sm" variant="ghost" aria-label="Download encrypted backup" render={<a href={`/api/v1/admin/backups/${b.id}/download`} />} nativeButton={false}>
                      <DownloadIcon />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
