"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LockIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/auth/field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";

type Profile = { display_name: string; bio: string | null; avatar_url: string | null; phone: string | null };

export function ProfileTab() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["profile"], queryFn: () => api<Profile>("/me/profile") });
  const [form, setForm] = useState<Profile | null>(null);
  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const save = useMutation({
    mutationFn: (p: Profile) =>
      api<Profile>("/me/profile", {
        method: "PATCH",
        body: { display_name: p.display_name, bio: p.bio || null, phone: p.phone || null },
      }),
    onSuccess: (p) => {
      qc.setQueryData(["profile"], p);
      qc.invalidateQueries({ queryKey: ["me"] });
      toast.success("Profile saved");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!form) return <div className="h-48 animate-pulse rounded-xl bg-muted" />;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Public profile</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate(form);
          }}
        >
          <Field label="Display name" name="display_name" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
          <div className="space-y-1.5">
            <Label htmlFor="bio">About you</Label>
            <Textarea id="bio" rows={4} maxLength={1000} value={form.bio ?? ""} onChange={(e) => setForm({ ...form, bio: e.target.value })} />
          </div>
          <Field
            label="Phone"
            name="phone"
            type="tel"
            value={form.phone ?? ""}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            hint="Only shared with hosts after a confirmed booking. Encrypted at rest (AES-256-GCM)."
          />
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <LockIcon className="size-3.5" /> Your email and phone never appear on public pages.
          </p>
          <Button type="submit" disabled={save.isPending}>
            Save
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
