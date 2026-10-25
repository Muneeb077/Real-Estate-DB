"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";

export function VerifyEmail() {
  const token = useSearchParams().get("token");
  const qc = useQueryClient();
  const [state, setState] = useState<{ ok?: boolean; error?: string }>({});
  const sent = useRef(false);

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true;
    api("/auth/verify-email", { body: { token } })
      .then(() => {
        setState({ ok: true });
        qc.invalidateQueries({ queryKey: ["me"] });
      })
      .catch((e) => setState({ error: errorMessage(e) }));
  }, [token, qc]);

  if (!token) return <p className="text-center text-muted-foreground">This link is missing its token.</p>;
  if (state.error) return <p className="text-center text-destructive">{state.error}</p>;
  if (!state.ok) return <p className="text-center text-muted-foreground">Verifying…</p>;
  return (
    <div className="space-y-4 text-center">
      <p>Your email is verified. You can now message hosts, make offers and book stays.</p>
      <Button render={<Link href="/" />} nativeButton={false}>
        Start exploring
      </Button>
    </div>
  );
}
