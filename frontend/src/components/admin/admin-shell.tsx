"use client";

import { RequireAuth } from "@/components/auth/require-auth";
import { SubNav } from "@/components/host/host-shell";

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
      {() => (
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
          <SubNav items={NAV} />
          {children}
        </div>
      )}
    </RequireAuth>
  );
}
