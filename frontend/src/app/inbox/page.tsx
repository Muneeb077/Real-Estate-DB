"use client";

import { useQuery } from "@tanstack/react-query";
import { LockIcon, MessageSquareIcon } from "lucide-react";
import Link from "next/link";

import { PageTitle, RequireAuth } from "@/components/auth/require-auth";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { shortDate } from "@/lib/format";

export type ConversationSummary = {
  public_id: string;
  listing_id: string;
  listing_title: string;
  listing_thumb: string | null;
  my_role: "guest" | "host";
  other_name: string;
  other_avatar: string | null;
  last_message: string;
  last_message_at: string;
  unread: boolean;
};

export default function InboxPage() {
  return <RequireAuth>{() => <Inbox />}</RequireAuth>;
}

function Inbox() {
  const { data = [], isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api<ConversationSummary[]>("/conversations"),
    refetchInterval: 15_000,
  });
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <PageTitle
        title="Inbox"
        description="Messages with hosts and guests."
        action={
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <LockIcon className="size-3.5" /> Encrypted at rest
          </span>
        }
      />
      {isLoading ? (
        <div className="h-40 animate-pulse rounded-xl bg-muted" />
      ) : data.length === 0 ? (
        <div className="py-20 text-center text-muted-foreground">
          <MessageSquareIcon className="mx-auto size-10" />
          <p className="mt-3">No conversations yet. Message a host from any listing.</p>
        </div>
      ) : (
        <ul className="divide-y rounded-xl border">
          {data.map((c) => (
            <li key={c.public_id}>
              <Link href={`/inbox/${c.public_id}`} className="flex items-center gap-4 p-4 hover:bg-muted/50">
                <Avatar className="size-11">
                  <AvatarImage src={c.other_avatar ?? undefined} alt="" />
                  <AvatarFallback>{c.other_name[0]}</AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={c.unread ? "font-semibold" : "font-medium"}>{c.other_name}</span>
                    <Badge variant="outline" className="text-xs">
                      {c.my_role === "host" ? "Guest" : "Host"}
                    </Badge>
                    {c.unread && <span className="size-2 rounded-full bg-primary" aria-label="unread" />}
                  </div>
                  <div className="truncate text-sm text-muted-foreground">{c.listing_title}</div>
                  <div className="truncate text-sm">{c.last_message}</div>
                </div>
                <div className="text-xs text-muted-foreground">{shortDate(c.last_message_at)}</div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
