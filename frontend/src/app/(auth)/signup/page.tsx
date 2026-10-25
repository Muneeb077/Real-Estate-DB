import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";

import { SignupForm } from "./signup-form";

export const metadata: Metadata = { title: "Sign up" };

export default function SignupPage() {
  return (
    <AuthCard title="Create your account" description="Browsing is free; an account lets you save, message and book.">
      <Suspense>
        <SignupForm />
      </Suspense>
    </AuthCard>
  );
}
