"use client";

import { ShieldCheckIcon } from "lucide-react";
import Link from "next/link";

import { RequireAuth } from "@/components/auth/require-auth";
import { SubNav } from "@/components/host/host-shell";
import { Button } from "@/components/ui/button";
import { useLogout } from "@/lib/auth";

const NAV = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/moderation", label: "Moderation" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/audit", label: "Audit log" },
  { href: "/admin/settings", label: "Settings & backups" },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth role="admin">
      {(me) => (
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
          <SubNav items={NAV} />
          {!me.mfa_enabled || !me.mfa_session ? <MfaGate enabled={me.mfa_enabled} /> : children}
        </div>
      )}
    </RequireAuth>
  );
}

function MfaGate({ enabled }: { enabled: boolean }) {
  const logout = useLogout();
  return (
    <div className="mx-auto max-w-lg py-16 text-center">
      <ShieldCheckIcon className="mx-auto size-10 text-primary" />
      <h1 className="mt-4 text-2xl font-semibold">Two-factor authentication required</h1>
      <p className="mt-2 text-muted-foreground">
        {enabled
          ? "This session wasn't verified with your authenticator. Sign in again and enter your code."
          : "Admins must turn on an authenticator app before using the console."}
      </p>
      <div className="mt-6">
        {enabled ? (
          <Button onClick={logout}>Sign in again</Button>
        ) : (
          <Button render={<Link href="/account" />} nativeButton={false}>
            Set up two-factor authentication
          </Button>
        )}
      </div>
    </div>
  );
}
