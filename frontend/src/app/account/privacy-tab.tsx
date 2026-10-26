"use client";

import { useQueryClient } from "@tanstack/react-query";
import { DownloadIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/auth/field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, errorMessage } from "@/lib/api";

export function PrivacyTab() {
  const [password, setPassword] = useState("");
  const router = useRouter();
  const qc = useQueryClient();
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Download your data</CardTitle>
          <CardDescription>Everything HomeNest stores about you, decrypted, as a JSON file.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" render={<a href="/api/v1/me/export" />} nativeButton={false}>
            <DownloadIcon /> Export my data
          </Button>
        </CardContent>
      </Card>
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Delete account</CardTitle>
          <CardDescription>
            Your personal data is erased. Messages and completed transactions stay, linked to an anonymous account.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!confirm("Delete your account permanently?")) return;
              try {
                await api("/me", { method: "DELETE", body: { password } });
                qc.clear();
                qc.setQueryData(["me"], null);
                router.push("/");
              } catch (err) {
                toast.error(errorMessage(err));
              }
            }}
          >
            <div className="w-64">
              <Field label="Confirm with your password" type="password" name="del-pw" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <Button variant="destructive" type="submit" disabled={!password}>
              Delete my account
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
