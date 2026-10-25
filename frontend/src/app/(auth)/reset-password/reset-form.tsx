"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/auth/field";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";

export function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/auth/reset-password", { body: { token, password } });
      toast.success("Password changed. Log in with your new password.");
      router.push("/login");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field
        label="New password"
        type="password"
        name="password"
        autoComplete="new-password"
        hint="10+ characters with upper- and lower-case letters and a number."
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Button type="submit" className="w-full" disabled={busy || !token}>
        Update password
      </Button>
    </form>
  );
}
