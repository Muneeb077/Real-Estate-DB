"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LockIcon, SearchIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AdminShell } from "@/components/admin/admin-shell";
import { PageTitle } from "@/components/auth/require-auth";
import { NativeSelect } from "@/components/search/filters-sheet";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, errorMessage } from "@/lib/api";
import { shortDate } from "@/lib/format";

type User = {
  public_id: string;
  email: string;
  display_name: string;
  status: string;
  roles: string[];
  verified: boolean;
  created_at: string;
  last_seen: string | null;
};

export default function AdminUsersPage() {
  return (
    <AdminShell>
      <Users />
    </AdminShell>
  );
}

function Users() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState({ q: "", role: "", status: "" });
  const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
  const { data = [], isLoading } = useQuery({ queryKey: ["admin-users", qs], queryFn: () => api<User[]>(`/admin/users?${qs}`) });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) => api(`/admin/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      toast.success("User updated (recorded in the audit log)");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const toggleRole = (u: User, role: string) =>
    update.mutate({ id: u.public_id, body: { roles: u.roles.includes(role) ? u.roles.filter((r) => r !== role) : [...u.roles, role] } });

  return (
    <>
      <PageTitle
        title="Users"
        description="Emails are decrypted for this view only, and each view is written to the audit log."
        action={
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <LockIcon className="size-3" /> Exact-email search uses the HMAC blind index
          </span>
        }
      />
      <form
        className="mb-4 flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setFilters((f) => ({ ...f, q }));
        }}
      >
        <Input className="w-72" aria-label="Search" placeholder="Exact email or part of a name" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" variant="outline">
          <SearchIcon /> Search
        </Button>
        <div className="w-36">
          <NativeSelect aria-label="Role" value={filters.role} onChange={(e) => setFilters({ ...filters, role: e.target.value })}>
            <option value="">All roles</option>
            <option value="guest">Guests</option>
            <option value="host">Hosts</option>
            <option value="admin">Admins</option>
          </NativeSelect>
        </div>
        <div className="w-36">
          <NativeSelect aria-label="Status" value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
          </NativeSelect>
        </div>
      </form>
      <div className="overflow-x-auto rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Roles</TableHead>
              <TableHead>Security</TableHead>
              <TableHead>Joined</TableHead>
              <TableHead>Status</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={6} className="text-muted-foreground">
                  Loading…
                </TableCell>
              </TableRow>
            )}
            {data.map((u) => (
              <TableRow key={u.public_id}>
                <TableCell>
                  <div className="font-medium">{u.display_name}</div>
                  <div className="text-xs text-muted-foreground">{u.email}</div>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    {["guest", "host", "admin"].map((r) => (
                      <button key={r} onClick={() => toggleRole(u, r)} title={`Toggle ${r}`}>
                        <Badge variant={u.roles.includes(r) ? "default" : "outline"} className="capitalize">
                          {r}
                        </Badge>
                      </button>
                    ))}
                  </div>
                </TableCell>
                <TableCell className="text-xs">
                  {u.verified ? "Email verified" : "Unverified"}
                </TableCell>
                <TableCell className="text-sm">{shortDate(u.created_at)}</TableCell>
                <TableCell>
                  <StatusBadge status={u.status} />
                </TableCell>
                <TableCell>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => update.mutate({ id: u.public_id, body: { status: u.status === "active" ? "suspended" : "active" } })}
                  >
                    {u.status === "active" ? "Suspend" : "Reactivate"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
