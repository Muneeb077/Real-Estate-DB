"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageTitle } from "@/components/auth/require-auth";
import { HostShell } from "@/components/host/host-shell";
import { EMPTY_LISTING, ListingForm } from "@/components/host/listing-form";
import { api, errorMessage } from "@/lib/api";

export default function NewListingPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  return (
    <HostShell>
      <div className="max-w-3xl">
        <PageTitle title="New listing" description="Save a draft, add photos, then submit it for review." />
        <ListingForm
          initial={EMPTY_LISTING}
          submitLabel="Save draft"
          busy={busy}
          onSubmit={async (v) => {
            setBusy(true);
            try {
              const r = await api<{ public_id: string }>("/host/listings", { body: v });
              toast.success("Draft saved. Now add photos.");
              router.push(`/host/listings/${r.public_id}`);
            } catch (e) {
              toast.error(errorMessage(e));
              setBusy(false);
            }
          }}
        />
      </div>
    </HostShell>
  );
}
