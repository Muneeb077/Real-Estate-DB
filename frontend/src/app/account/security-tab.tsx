"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LaptopIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/auth/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, errorMessage } from "@/lib/api";
import { shortDate } from "@/lib/format";

type Session = { family_id: string; user_agent: string; ip: string; signed_in_at: string; last_active_at: string; current: boolean };

export function SecurityTab() {
  return (
    <div className="space-y-6">
      <ChangePassword />
      <Sessions />
    </div>
  );
}

function ChangePassword() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = useMutation({
    mutationFn: () => api("/auth/change-password", { body: { current_password: current, new_password: next } }),
    onSuccess: () => {
      toast.success("Password changed. Other devices were signed out.");
      setCurrent("");
      setNext("");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
        <CardDescription>Stored as an Argon2id hash. Changing it signs out your other sessions.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            change.mutate();
          }}
        >
          <Field label="Current password" type="password" name="current" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          <Field label="New password" type="password" name="new" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
          <div>
            <Button type="submit" disabled={!current || !next || change.isPending}>
              Change password
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function Sessions() {
  const qc = useQueryClient();
  const { data = [] } = useQuery({ queryKey: ["sessions"], queryFn: () => api<Session[]>("/auth/sessions") });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/auth/sessions/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sessions"] }),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Where you&apos;re signed in</CardTitle>
        <CardDescription>Refresh tokens rotate on every use; reusing an old one signs that device out everywhere.</CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        {data.map((s) => (
          <div key={s.family_id} className="flex items-center gap-3 py-3">
            <LaptopIcon className="size-5 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{s.user_agent || "Unknown device"}</div>
              <div className="text-xs text-muted-foreground">
                {s.ip} · signed in {shortDate(s.signed_in_at)} · active {shortDate(s.last_active_at)}
              </div>
            </div>
            {s.current ? (
              <Badge variant="secondary">This device</Badge>
            ) : (
              <Button variant="outline" size="sm" onClick={() => revoke.mutate(s.family_id)}>
                Sign out
              </Button>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
