"use client";

import { usePathname, useRouter } from "next/navigation";
import { Suspense, useEffect } from "react";

import { hasRole, useMe } from "@/lib/auth";
import type { Me, Role } from "@/lib/types";

/**
 * Client-side gate for signed-in pages. The API enforces every rule itself;
 * this only decides what to render and where to send anonymous visitors.
 */
type Props = { role?: Role; children: (me: Me) => React.ReactNode };

const Placeholder = () => <div className="mx-auto h-64 max-w-5xl animate-pulse px-4 py-10" />;

// Reading the URL is request-time data under Cache Components, so the gate renders inside Suspense.
export function RequireAuth(props: Props) {
  return (
    <Suspense fallback={<Placeholder />}>
      <Gate {...props} />
    </Suspense>
  );
}

function Gate({ role, children }: Props) {
  const { data: me, isLoading } = useMe();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !me) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [isLoading, me, pathname, router]);

  if (isLoading || !me) return <Placeholder />;
  if (role && !hasRole(me, role)) {
    return (
      <div className="mx-auto max-w-xl px-4 py-24 text-center">
        <h1 className="text-2xl font-semibold">No access</h1>
        <p className="mt-2 text-muted-foreground">This area needs the {role} role.</p>
      </div>
    );
  }
  return <>{children(me)}</>;
}

export function PageTitle({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}
