"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { RequireAuth } from "@/components/auth/require-auth";
import { cn } from "cn";

const NAV = [
  { href: "/host", label: "Dashboard" },
  { href: "/host/listings", label: "Listings" },
  { href: "/host/bookings", label: "Bookings" },
  { href: "/host/requests", label: "Offers & viewings" },
];

export function HostShell({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth role="host">
      {() => (
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
          <SubNav items={NAV} />
          {children}
        </div>
      )}
    </RequireAuth>
  );
}

export function SubNav({ items }: { items: { href: string; label: string }[] }) {
  const pathname = usePathname();
  return (
    <nav className="mb-8 flex gap-1 overflow-x-auto border-b">
      {items.map((n) => {
        const active = n.href === pathname || (n.href !== items[0].href && pathname.startsWith(n.href));
        return (
          <Link
            key={n.href}
            href={n.href}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap",
              active ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {n.label}
          </Link>
        );
      })}
    </nav>
  );
}
