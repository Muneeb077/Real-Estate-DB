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
  display_name: z.string().min(2, "At least 2 characters").max(120),
  email: z.email("Enter a valid email"),
  password: z
    .string()
    .min(10, "At least 10 characters")
    .regex(/[a-z]/, "Add a lower-case letter")
    .regex(/[A-Z]/, "Add an upper-case letter")
    .regex(/\d/, "Add a number"),
});

export function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const form = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: z.infer<typeof schema>) {
    try {
      const me = await api<Me>("/auth/signup", { body: values });
      qc.setQueryData(["me"], me);
      toast.success("Welcome! Check your email to verify your address.");
      router.push(safeNext(params.get("next")));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field label="Name" autoComplete="name" {...form.register("display_name")} error={errors.display_name?.message} />
      <Field label="Email" type="email" autoComplete="email" {...form.register("email")} error={errors.email?.message} />
      <Field
        label="Password"
        type="password"
        autoComplete="new-password"
        hint="10+ characters with upper- and lower-case letters and a number. Stored as an Argon2id hash."
        {...form.register("password")}
        error={errors.password?.message}
      />
      <Button className="w-full" type="submit" disabled={isSubmitting}>
        Create account
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-foreground hover:underline">
          Log in
        </Link>
      </p>
    </form>
  );
}
