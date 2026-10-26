import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return (
    <AuthCard title="Welcome back" description="Log in to save homes, message hosts and book stays.">
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
