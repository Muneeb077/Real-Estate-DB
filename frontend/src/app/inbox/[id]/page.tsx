"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeftIcon, SendIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { RequireAuth } from "@/components/auth/require-auth";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { cn } from "cn";

type Thread = {
  public_id: string;
  listing: { public_id: string; title: string };
  other: { name: string; avatar_url: string | null };
  messages: { id: number; body: string; created_at: string; mine: boolean; sender_name: string }[];
};

export default function ThreadPage() {
  return <RequireAuth>{() => <ThreadView />}</RequireAuth>;
}

function ThreadView() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const { data } = useQuery({
    queryKey: ["conversation", id],
    queryFn: () => api<Thread>(`/conversations/${id}`),
    refetchInterval: 8_000,
  });
  const send = useMutation({
    mutationFn: () => api(`/conversations/${id}/messages`, { body: { message: text } }),
    onSuccess: () => {
      setText("");
      qc.invalidateQueries({ queryKey: ["conversation", id] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [data?.messages.length]);

  if (!data) return <div className="mx-auto h-96 max-w-3xl animate-pulse px-4 py-10" />;
  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-3xl flex-col px-4 sm:px-6">
      <div className="flex items-center gap-3 border-b py-4">
        <Button variant="ghost" size="icon" render={<Link href="/inbox" aria-label="Back to inbox" />} nativeButton={false}>
          <ArrowLeftIcon />
        </Button>
        <div>
          <div className="font-semibold">{data.other.name}</div>
          <Link href={`/listings/${data.listing.public_id}`} className="text-sm text-muted-foreground hover:underline">
            {data.listing.title}
          </Link>
        </div>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto py-6" aria-live="polite">
        {data.messages.map((m) => (
          <div key={m.id} className={cn("flex", m.mine ? "justify-end" : "justify-start")}>
            <div
              className={cn(
                "max-w-[75%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap",
                m.mine ? "bg-primary text-primary-foreground" : "bg-muted",
              )}
            >
              {m.body}
              <div className={cn("mt-1 text-[10px]", m.mine ? "text-primary-foreground/70" : "text-muted-foreground")}>
                {new Date(m.created_at).toLocaleString()}
              </div>
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <form
        className="flex gap-2 border-t py-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) send.mutate();
        }}
      >
        <Textarea
          aria-label="Message"
          rows={2}
          value={text}
          maxLength={4000}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (text.trim()) send.mutate();
            }
          }}
          placeholder="Write a message…"
        />
        <Button type="submit" size="icon" className="h-auto w-12" disabled={!text.trim() || send.isPending} aria-label="Send">
          <SendIcon />
        </Button>
      </form>
    </div>
  );
}
