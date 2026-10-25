"use client";

import { useQueryClient } from "@tanstack/react-query";
import { BuildingIcon, LockIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/auth/field";
import { RequireAuth } from "@/components/auth/require-auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, errorMessage } from "@/lib/api";
import { hasRole } from "@/lib/auth";

export default function HostOnboardingPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [form, setForm] = useState({ agency_name: "", license_number: "", phone: "" });
  const [busy, setBusy] = useState(false);

  return (
    <RequireAuth>
      {(me) =>
        hasRole(me, "host") ? (
          <div className="mx-auto max-w-xl px-4 py-24 text-center">
            <p className="text-lg">You&apos;re already a host.</p>
            <Button className="mt-4" onClick={() => router.push("/host")}>
              Go to dashboard
            </Button>
          </div>
        ) : (
          <div className="mx-auto max-w-xl px-4 py-12">
            <Card>
              <CardHeader>
                <BuildingIcon className="size-8 text-primary" />
                <CardTitle className="text-2xl">Become a host</CardTitle>
                <CardDescription>
                  List homes for sale, long-term rent or short stays. Add a license number to get the verified badge
                  after an admin review.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form
                  className="space-y-4"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setBusy(true);
                    try {
                      await api("/host/onboarding", {
                        body: {
                          agency_name: form.agency_name || null,
                          license_number: form.license_number || null,
                          phone: form.phone,
                        },
                      });
                      await qc.invalidateQueries({ queryKey: ["me"] });
                      toast.success("Welcome, host!");
                      router.push("/host");
                    } catch (err) {
                      toast.error(errorMessage(err));
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <Field label="Agency name (optional)" name="agency" value={form.agency_name} onChange={(e) => setForm({ ...form, agency_name: e.target.value })} />
                  <Field label="Real-estate license number (optional)" name="license" value={form.license_number} onChange={(e) => setForm({ ...form, license_number: e.target.value })} />
                  <Field label="Phone" name="phone" type="tel" required value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <LockIcon className="size-3.5" /> License and phone are encrypted with per-record keys (AES-256-GCM).
                  </p>
                  <Button type="submit" className="w-full" disabled={busy || !form.phone}>
                    Start hosting
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        )
      }
    </RequireAuth>
  );
}
