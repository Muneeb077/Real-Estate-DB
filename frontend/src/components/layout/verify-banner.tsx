"use client";

import { MailIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { api, errorMessage } from "@/lib/api";
import { useMe } from "@/lib/auth";

export function VerifyBanner() {
  const { data: me } = useMe();
  const [sent, setSent] = useState(false);
  if (!me || me.email_verified) return null;
  return (
    <div className="border-b bg-amber-500/10 px-4 py-2 text-center text-sm">
      <MailIcon className="mr-1 inline size-4" /> Verify your email to message hosts, make offers and book.{" "}
      {sent ? (
        <span className="text-muted-foreground">Link sent. Check your inbox.</span>
      ) : (
        <button
          className="font-medium underline"
          onClick={async () => {
            try {
              await api("/auth/resend-verification", { method: "POST" });
              setSent(true);
            } catch (e) {
              toast.error(errorMessage(e));
            }
          }}
        >
          Resend link
        </button>
      )}
    </div>
  );
}
