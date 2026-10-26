"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellIcon } from "lucide-react";
import Link from "next/link";

import { PageTitle, RequireAuth } from "@/components/auth/require-auth";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { cn } from "cn";

type Notification = { id: number; kind: string; title: string; link: string | null; read_at: string | null; created_at: string };

export default function NotificationsPage() {
  return <RequireAuth>{() => <Notifications />}</RequireAuth>;
}

function Notifications() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<{ items: Notification[]; unread: number }>("/me/notifications"),
  });
  const markRead = useMutation({
    mutationFn: () => api("/me/notifications/read", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <PageTitle
        title="Notifications"
        action={
          data?.unread ? (
            <Button variant="outline" onClick={() => markRead.mutate()}>
              Mark all as read
            </Button>
          ) : null
        }
      />
      {!data?.items.length ? (
        <div className="py-20 text-center text-muted-foreground">
          <BellIcon className="mx-auto size-10" />
          <p className="mt-3">You&apos;re all caught up.</p>
        </div>
      ) : (
        <ul className="divide-y rounded-xl border">
          {data.items.map((n) => (
            <li key={n.id}>
              <Link href={n.link ?? "#"} className={cn("flex items-start gap-3 p-4 hover:bg-muted/50", !n.read_at && "bg-primary/5")}>
                <span className={cn("mt-2 size-2 shrink-0 rounded-full", n.read_at ? "bg-transparent" : "bg-primary")} />
                <div className="flex-1">
                  <div className="text-sm">{n.title}</div>
                  <div className="text-xs text-muted-foreground">{shortDate(n.created_at)}</div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
