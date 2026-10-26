"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownIcon, ArrowUpIcon, ExternalLinkIcon, ImagePlusIcon, TrashIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Field } from "@/components/auth/field";
import { PageTitle } from "@/components/auth/require-auth";
import { HostShell } from "@/components/host/host-shell";
import { ListingForm, type ListingFormValue } from "@/components/host/listing-form";
import { ListingImage } from "@/components/listing/listing-image";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { isoDate } from "@/components/search/date-range-picker";
import { api, ApiError, errorMessage } from "@/lib/api";
import { money, shortDate } from "@/lib/format";

type Editable = ListingFormValue & {
  public_id: string;
  status: string;
  version: number;
  moderation_note: string | null;
  photos: { id: number; url: string; thumb_url: string | null; sort_order: number }[];
  blocked_dates: string[];
  price_rules: { id: number; label: string; start_date: string; end_date: string; nightly_price: number; weekends_only: number }[];
};

export default function EditListingPage() {
  return (
    <HostShell>
      <Editor />
    </HostShell>
  );
}

function Editor() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const key = ["host-listing", id];
  const { data, refetch } = useQuery({ queryKey: key, queryFn: () => api<Editable>(`/host/listings/${id}`) });
  const reload = () => {
    qc.invalidateQueries({ queryKey: key });
    qc.invalidateQueries({ queryKey: ["host-listings"] });
  };

  const save = useMutation({
    mutationFn: (v: ListingFormValue) => api(`/host/listings/${id}`, { method: "PUT", body: { ...v, version: data!.version } }),
    onSuccess: () => {
      toast.success("Saved");
      reload();
    },
    onError: (e) => {
      if (e instanceof ApiError && e.code === "version_conflict") {
        toast.error(e.message, { action: { label: "Reload", onClick: () => refetch() } });
      } else toast.error(errorMessage(e));
    },
  });
  const status = useMutation({
    mutationFn: (action: string) => api<{ status: string }>(`/host/listings/${id}/status`, { body: { action } }),
    onSuccess: (r) => {
      toast.success(r.status === "pending_review" ? "Submitted for review" : `Listing ${r.status.replace("_", " ")}`);
      reload();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!data) return <div className="h-96 animate-pulse rounded-xl bg-muted" />;
  const { photos, blocked_dates, price_rules, status: st, version, moderation_note, public_id, ...form } = data;
  void version;

  return (
    <div className="max-w-4xl">
      <PageTitle
        title={data.title}
        description={`Version ${data.version}`}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={st} />
            {["draft", "rejected"].includes(st) && <Button onClick={() => status.mutate("submit")}>Submit for review</Button>}
            {st === "published" && (
              <>
                <Button variant="outline" render={<Link href={`/listings/${public_id}`} />} nativeButton={false}>
                  <ExternalLinkIcon /> View
                </Button>
                <Button variant="outline" onClick={() => status.mutate("pause")}>
                  Pause
                </Button>
              </>
            )}
            {st === "paused" && <Button onClick={() => status.mutate("resume")}>Resume</Button>}
            {!["archived", "sold", "rented"].includes(st) && (
              <Button variant="ghost" onClick={() => confirm("Archive this listing?") && status.mutate("archive")}>
                Archive
              </Button>
            )}
          </div>
        }
      />
      {st === "rejected" && moderation_note && (
        <p className="mb-6 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm">Moderator note: {moderation_note}</p>
      )}
      <Tabs defaultValue="details">
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="photos">Photos ({photos.length})</TabsTrigger>
          {data.listing_mode === "short_term_stay" && <TabsTrigger value="calendar">Calendar & pricing</TabsTrigger>}
        </TabsList>
        <TabsContent value="details" className="pt-4">
          <ListingForm key={data.version} initial={form} submitLabel="Save changes" busy={save.isPending} onSubmit={(v) => save.mutate(v)} />
        </TabsContent>
        <TabsContent value="photos" className="pt-4">
          <Photos id={id} photos={photos} onChange={reload} />
        </TabsContent>
        <TabsContent value="calendar" className="pt-4">
          <CalendarTab id={id} blocked={blocked_dates} rules={price_rules} basePrice={data.price} onChange={reload} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Photos({ id, photos, onChange }: { id: string; photos: Editable["photos"]; onChange: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  async function upload(files: FileList) {
    setUploading(true);
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      try {
        await api(`/host/listings/${id}/photos`, { form });
      } catch (e) {
        toast.error(`${file.name}: ${errorMessage(e)}`);
      }
    }
    setUploading(false);
    onChange();
  }
  async function move(index: number, delta: number) {
    const ids = photos.map((p) => p.id);
    const [moved] = ids.splice(index, 1);
    ids.splice(index + delta, 0, moved);
    await api(`/host/listings/${id}/photos/order`, { method: "PUT", body: { photo_ids: ids } });
    onChange();
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Photos</CardTitle>
        <CardDescription>
          JPEG, PNG or WebP up to 8 MB. Images are re-encoded to WebP and stripped of EXIF metadata (GPS, camera serials).
          The first photo is the cover.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {photos.map((p, i) => (
            <div key={p.id} className="group relative aspect-[4/3] overflow-hidden rounded-lg border">
              <ListingImage src={p.thumb_url ?? p.url} alt="" sizes="200px" />
              {i === 0 && <span className="absolute top-1 left-1 rounded bg-background/90 px-1.5 text-xs font-medium">Cover</span>}
              <div className="absolute right-1 bottom-1 flex gap-1">
                <Button size="icon-xs" variant="secondary" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Move earlier">
                  <ArrowUpIcon />
                </Button>
                <Button size="icon-xs" variant="secondary" disabled={i === photos.length - 1} onClick={() => move(i, 1)} aria-label="Move later">
                  <ArrowDownIcon />
                </Button>
                <Button
                  size="icon-xs"
                  variant="destructive"
                  aria-label="Delete photo"
                  onClick={async () => {
                    await api(`/host/listings/${id}/photos/${p.id}`, { method: "DELETE" });
                    onChange();
                  }}
                >
                  <TrashIcon />
                </Button>
              </div>
            </div>
          ))}
          <button
            type="button"
            onClick={() => input.current?.click()}
            disabled={uploading}
            className="flex aspect-[4/3] flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-sm text-muted-foreground hover:bg-muted/50"
          >
            <ImagePlusIcon className="size-6" />
            {uploading ? "Uploading…" : "Add photos"}
          </button>
        </div>
        <input
          ref={input}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          hidden
          onChange={(e) => e.target.files?.length && upload(e.target.files)}
        />
      </CardContent>
    </Card>
  );
}

function CalendarTab({
  id,
  blocked,
  rules,
  basePrice,
  onChange,
}: {
  id: string;
  blocked: string[];
  rules: Editable["price_rules"];
  basePrice: number;
  onChange: () => void;
}) {
  const [selected, setSelected] = useState<Date[]>(blocked.map((d) => new Date(`${d}T00:00`)));
  const [rule, setRule] = useState({ label: "", start_date: "", end_date: "", nightly_price: "", weekends_only: false });

  async function saveBlocked() {
    const now = new Set(selected.map((d) => isoDate(d)!));
    const before = new Set(blocked);
    try {
      await api(`/host/listings/${id}/calendar`, {
        method: "PUT",
        body: { block: [...now].filter((d) => !before.has(d)), unblock: [...before].filter((d) => !now.has(d)) },
      });
      toast.success("Calendar updated");
      onChange();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }
  async function addRule(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api(`/host/listings/${id}/price-rules`, { body: { ...rule, nightly_price: Number(rule.nightly_price) } });
      setRule({ label: "", start_date: "", end_date: "", nightly_price: "", weekends_only: false });
      onChange();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Blocked dates</CardTitle>
          <CardDescription>Click days to close them. Booked nights are protected separately by the database.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Calendar mode="multiple" selected={selected} onSelect={(d) => setSelected(d ?? [])} disabled={{ before: new Date() }} numberOfMonths={1} />
          <Button onClick={saveBlocked}>Save calendar</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Seasonal & weekend pricing</CardTitle>
          <CardDescription>
            Base price {money(basePrice)}/night. For each night the most specific rule wins (computed by the CalcStaySubtotal
            SQL function).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ul className="divide-y rounded-lg border text-sm">
            {rules.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-2 p-2">
                <span>
                  <span className="font-medium">{r.label}</span> · {shortDate(r.start_date)} – {shortDate(r.end_date)}
                  {r.weekends_only ? " · Fri & Sat" : ""} · {money(r.nightly_price)}
                </span>
                <Button
                  size="icon-xs"
                  variant="ghost"
                  aria-label="Delete rule"
                  onClick={async () => {
                    await api(`/host/listings/${id}/price-rules/${r.id}`, { method: "DELETE" });
                    onChange();
                  }}
                >
                  <TrashIcon />
                </Button>
              </li>
            ))}
            {!rules.length && <li className="p-2 text-muted-foreground">No rules yet.</li>}
          </ul>
          <form onSubmit={addRule} className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <Field label="Label" name="rule-label" required value={rule.label} onChange={(e) => setRule({ ...rule, label: e.target.value })} placeholder="Summer peak" />
            </div>
            <Field label="From" name="rule-start" type="date" required value={rule.start_date} onChange={(e) => setRule({ ...rule, start_date: e.target.value })} />
            <Field label="To" name="rule-end" type="date" required value={rule.end_date} onChange={(e) => setRule({ ...rule, end_date: e.target.value })} />
            <Field label="Nightly price" name="rule-price" type="number" min={1} required value={rule.nightly_price} onChange={(e) => setRule({ ...rule, nightly_price: e.target.value })} />
            <label className="flex items-end gap-2 pb-2 text-sm">
              <Checkbox checked={rule.weekends_only} onCheckedChange={(c) => setRule({ ...rule, weekends_only: !!c })} /> Weekends only
            </label>
            <Button type="submit" className="col-span-2">
              Add rule
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
