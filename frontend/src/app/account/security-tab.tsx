"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LaptopIcon, ShieldCheckIcon } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/auth/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, errorMessage } from "@/lib/api";
import { shortDate } from "@/lib/format";
import type { Me } from "@/lib/types";

type Session = { family_id: string; user_agent: string; ip: string; signed_in_at: string; last_active_at: string; current: boolean };

export function SecurityTab({ me }: { me: Me }) {
  return (
    <div className="space-y-6">
      <ChangePassword />
      <TwoFactor me={me} />
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

function TwoFactor({ me }: { me: Me }) {
  const qc = useQueryClient();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);

  const start = useMutation({
    mutationFn: () => api<{ secret: string; otpauth_uri: string }>("/auth/mfa/setup", { method: "POST" }),
    onSuccess: setSetup,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const enable = useMutation({
    mutationFn: () => api<Me & { recovery_codes: string[] }>("/auth/mfa/enable", { body: { code } }),
    onSuccess: (res) => {
      setRecovery(res.recovery_codes);
      setSetup(null);
      setCode("");
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const disable = useMutation({
    mutationFn: () => api("/auth/mfa/disable", { body: { password, code } }),
    onSuccess: () => {
      toast.success("Two-factor authentication turned off");
      setCode("");
      setPassword("");
      qc.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Two-factor authentication
          {me.mfa_enabled && (
            <Badge className="bg-emerald-600 text-white">
              <ShieldCheckIcon /> On
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          Time-based one-time codes (TOTP). Required for admins. The secret is encrypted at rest and codes can&apos;t be
          replayed.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {recovery && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4">
            <p className="font-medium">Save these recovery codes now. They won&apos;t be shown again.</p>
            <ul className="mt-2 grid grid-cols-2 gap-1 font-mono text-sm">
              {recovery.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        )}
        {me.mfa_enabled ? (
          <form
            className="grid gap-4 sm:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              disable.mutate();
            }}
          >
            <Field label="Password" type="password" name="mfa-pw" value={password} onChange={(e) => setPassword(e.target.value)} />
            <Field label="Current code" name="mfa-code" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} />
            <div className="flex items-end">
              <Button variant="destructive" type="submit" disabled={!password || !code}>
                Turn off
              </Button>
            </div>
          </form>
        ) : setup ? (
          <div className="flex flex-col gap-6 sm:flex-row">
            <div className="rounded-lg bg-white p-3">
              <QRCodeSVG value={setup.otpauth_uri} size={160} />
            </div>
            <form
              className="flex-1 space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                enable.mutate();
              }}
            >
              <p className="text-sm text-muted-foreground">
                Scan with Google Authenticator, 1Password or Authy, or enter{" "}
                <code className="rounded bg-muted px-1">{setup.secret}</code>
              </p>
              <Field label="Enter the 6-digit code" name="enable-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />
              <Button type="submit" disabled={code.length < 6 || enable.isPending}>
                Turn on
              </Button>
            </form>
          </div>
        ) : (
          <Button onClick={() => start.mutate()} disabled={start.isPending}>
            Set up authenticator app
          </Button>
        )}
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
