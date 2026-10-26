"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
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

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const next = safeNext(params.get("next"));

  function done(me: Me) {
    qc.setQueryData(["me"], me);
    qc.invalidateQueries({ queryKey: ["favorite-ids"] });
    router.push(next);
  }

  async function onSubmit(values: z.infer<typeof schema>) {
    try {
      done(await api<Me>("/auth/login", { body: values }));
    } catch (e) {
      toast.error(errorMessage(e));
    }
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
