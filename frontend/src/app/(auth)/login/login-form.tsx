"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Field } from "@/components/auth/field";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { safeNext } from "@/lib/safe-next";
import type { Me } from "@/lib/types";

const schema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Enter your password"),
});

type LoginResponse = Me | { mfa_required: true; mfa_token: string };

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const next = safeNext(params.get("next"));

  function done(me: Me) {
    qc.setQueryData(["me"], me);
    qc.invalidateQueries({ queryKey: ["favorite-ids"] });
    router.push(next);
  }

  async function onSubmit(values: z.infer<typeof schema>) {
    try {
      const res = await api<LoginResponse>("/auth/login", { body: values });
      if ("mfa_required" in res) setMfaToken(res.mfa_token);
      else done(res);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      done(
        await api<Me>("/auth/mfa/verify", {
          body: { mfa_token: mfaToken, ...(useRecovery ? { recovery_code: code } : { code }) },
        }),
      );
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (mfaToken) {
    return (
      <form onSubmit={verify} className="space-y-4">
        <Field
          label={useRecovery ? "Recovery code" : "6-digit code from your authenticator app"}
          name="code"
          autoComplete="one-time-code"
          inputMode={useRecovery ? "text" : "numeric"}
          autoFocus
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <Button className="w-full" type="submit" disabled={busy || !code}>
          Verify
        </Button>
        <button type="button" className="w-full text-sm text-muted-foreground underline" onClick={() => setUseRecovery(!useRecovery)}>
          {useRecovery ? "Use authenticator code" : "Use a recovery code instead"}
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field label="Email" type="email" autoComplete="email" {...form.register("email")} error={form.formState.errors.email?.message} />
      <Field
        label="Password"
        type="password"
        autoComplete="current-password"
        {...form.register("password")}
        error={form.formState.errors.password?.message}
      />
      <Button className="w-full" type="submit" disabled={form.formState.isSubmitting}>
        Log in
      </Button>
      <div className="flex justify-between text-sm">
        <Link href="/forgot-password" className="text-muted-foreground hover:underline">
          Forgot password?
        </Link>
        <Link href={`/signup${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-medium hover:underline">
          Create an account
        </Link>
      </div>
    </form>
  );
}
