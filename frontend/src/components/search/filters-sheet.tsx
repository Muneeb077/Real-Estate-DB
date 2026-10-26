"use client";

import { useQuery } from "@tanstack/react-query";
import { SlidersHorizontalIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api } from "@/lib/api";
import type { Amenity } from "@/lib/types";

export const PROPERTY_TYPES = ["house", "apartment", "condo", "townhouse", "villa", "cabin", "studio", "loft"];

export type Filters = Record<string, string | undefined>;

export function NativeSelect(props: React.ComponentProps<"select">) {
  return (
    <select
      {...props}
      className="h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    />
  );
}

export function FiltersSheet({ value, onApply }: { value: Filters; onApply: (f: Filters) => void }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Filters>(value);
  const { data: amenities = [] } = useQuery({
    queryKey: ["amenities"],
    queryFn: () => api<Amenity[]>("/amenities"),
    staleTime: Infinity,
  });
  const selected = new Set((draft.amenities ?? "").split(",").filter(Boolean));
  const set = (k: string, v: string | undefined) => setDraft((d) => ({ ...d, [k]: v || undefined }));
  const active = ["type", "min_price", "max_price", "beds", "baths", "amenities"].filter((k) => value[k]).length;

  return (
    <Sheet
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) setDraft(value);
      }}
    >
      <SheetTrigger render={<Button variant="outline" />}>
        <SlidersHorizontalIcon /> Filters{active ? ` (${active})` : ""}
      </SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Filters</SheetTitle>
        </SheetHeader>
        <div className="space-y-6 px-4">
          <div className="space-y-2">
            <Label htmlFor="f-type">Property type</Label>
            <NativeSelect id="f-type" value={draft.type ?? ""} onChange={(e) => set("type", e.target.value)}>
              <option value="">Any</option>
              {PROPERTY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t[0].toUpperCase() + t.slice(1)}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-2">
            <Label>Price range</Label>
            <div className="flex gap-2">
              <Input
                aria-label="Minimum price"
                type="number"
                min={0}
                placeholder="Min"
                value={draft.min_price ?? ""}
                onChange={(e) => set("min_price", e.target.value)}
              />
              <Input
                aria-label="Maximum price"
                type="number"
                min={0}
                placeholder="Max"
                value={draft.max_price ?? ""}
                onChange={(e) => set("max_price", e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="f-beds">Bedrooms</Label>
              <NativeSelect id="f-beds" value={draft.beds ?? ""} onChange={(e) => set("beds", e.target.value)}>
                <option value="">Any</option>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}+
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-2">
              <Label htmlFor="f-baths">Bathrooms</Label>
              <NativeSelect id="f-baths" value={draft.baths ?? ""} onChange={(e) => set("baths", e.target.value)}>
                <option value="">Any</option>
                {[1, 2, 3, 4].map((n) => (
                  <option key={n} value={n}>
                    {n}+
                  </option>
                ))}
              </NativeSelect>
            </div>
          </div>
          <fieldset className="space-y-3">
            <legend className="text-sm font-medium">Amenities</legend>
            <div className="grid grid-cols-2 gap-2">
              {amenities.map((a) => (
                <label key={a.code} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={selected.has(a.code)}
                    onCheckedChange={(c) => {
                      const next = new Set(selected);
                      if (c) next.add(a.code);
                      else next.delete(a.code);
                      set("amenities", [...next].join(","));
                    }}
                  />
                  {a.label}
                </label>
              ))}
            </div>
          </fieldset>
        </div>
        <SheetFooter className="flex-row justify-between">
          <Button
            variant="ghost"
            onClick={() =>
              setDraft({ ...draft, type: undefined, min_price: undefined, max_price: undefined, beds: undefined, baths: undefined, amenities: undefined })
            }
          >
            Clear
          </Button>
          <Button
            onClick={() => {
              onApply(draft);
              setOpen(false);
            }}
          >
            Show results
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
