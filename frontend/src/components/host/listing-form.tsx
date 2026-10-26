"use client";

import { useQuery } from "@tanstack/react-query";
import { LockIcon } from "lucide-react";
import { useState } from "react";

import { Field } from "@/components/auth/field";
import { NativeSelect, PROPERTY_TYPES } from "@/components/search/filters-sheet";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { Amenity, ListingMode } from "@/lib/types";

import { LocationPicker } from "./location-picker";

export type ListingFormValue = {
  title: string;
  description: string;
  listing_mode: ListingMode;
  property_type: string;
  bedrooms: number;
  bathrooms: number;
  max_guests: number | null;
  size_sqft: number | null;
  price: number;
  currency: string;
  amenities: string[];
  address: { street: string; city: string; state: string | null; postal_code: string | null; country: string; lat: number; lng: number };
};

export const EMPTY_LISTING: ListingFormValue = {
  title: "",
  description: "",
  listing_mode: "short_term_stay",
  property_type: "apartment",
  bedrooms: 1,
  bathrooms: 1,
  max_guests: 2,
  size_sqft: null,
  price: 100,
  currency: "USD",
  amenities: ["wifi"],
  address: { street: "", city: "", state: null, postal_code: null, country: "US", lat: 40.7128, lng: -74.006 },
};

const PRICE_LABEL: Record<ListingMode, string> = {
  short_term_stay: "Nightly price",
  long_term_rent: "Monthly rent",
  sale: "Asking price",
};

export function ListingForm({
  initial,
  submitLabel,
  busy,
  onSubmit,
}: {
  initial: ListingFormValue;
  submitLabel: string;
  busy?: boolean;
  onSubmit: (v: ListingFormValue) => void;
}) {
  const [v, setV] = useState<ListingFormValue>(initial);
  const { data: amenities = [] } = useQuery({ queryKey: ["amenities"], queryFn: () => api<Amenity[]>("/amenities"), staleTime: Infinity });
  const set = <K extends keyof ListingFormValue>(k: K, val: ListingFormValue[K]) => setV((p) => ({ ...p, [k]: val }));
  const setAddr = (k: keyof ListingFormValue["address"], val: string | number | null) =>
    setV((p) => ({ ...p, address: { ...p.address, [k]: val } }));
  const num = (s: string) => (s === "" ? null : Number(s));

  return (
    <form
      className="space-y-6"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(v);
      }}
    >
      <Card>
        <CardHeader>
          <CardTitle>Basics</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="lf-mode">Listing type</Label>
            <NativeSelect id="lf-mode" value={v.listing_mode} onChange={(e) => set("listing_mode", e.target.value as ListingMode)}>
              <option value="short_term_stay">Short-term stay (nightly)</option>
              <option value="long_term_rent">Long-term rental (monthly)</option>
              <option value="sale">For sale</option>
            </NativeSelect>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="lf-type">Property type</Label>
            <NativeSelect id="lf-type" value={v.property_type} onChange={(e) => set("property_type", e.target.value)}>
              {PROPERTY_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t[0].toUpperCase() + t.slice(1)}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="sm:col-span-2">
            <Field label="Title" name="title" required minLength={10} maxLength={140} value={v.title} onChange={(e) => set("title", e.target.value)} hint="10–140 characters" />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="lf-desc">Description</Label>
            <Textarea id="lf-desc" rows={6} required minLength={50} maxLength={5000} value={v.description} onChange={(e) => set("description", e.target.value)} />
            <p className="text-xs text-muted-foreground">At least 50 characters. Searchable through the MySQL full-text index.</p>
          </div>
          <Field label="Bedrooms" name="bedrooms" type="number" min={0} max={30} value={v.bedrooms} onChange={(e) => set("bedrooms", Number(e.target.value))} />
          <Field label="Bathrooms" name="bathrooms" type="number" min={0.5} step={0.5} max={30} value={v.bathrooms} onChange={(e) => set("bathrooms", Number(e.target.value))} />
          <Field label="Size (sqft)" name="size" type="number" min={100} value={v.size_sqft ?? ""} onChange={(e) => set("size_sqft", num(e.target.value))} />
          {v.listing_mode === "short_term_stay" && (
            <Field label="Max guests" name="guests" type="number" min={1} max={50} required value={v.max_guests ?? ""} onChange={(e) => set("max_guests", num(e.target.value))} />
          )}
          <Field label={`${PRICE_LABEL[v.listing_mode]} (${v.currency})`} name="price" type="number" min={1} required value={v.price} onChange={(e) => set("price", Number(e.target.value))} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Location</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="Street address" name="street" required value={v.address.street} onChange={(e) => setAddr("street", e.target.value)} />
            <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
              <LockIcon className="size-3" /> Encrypted at rest; shown to guests only after a confirmed booking.
            </p>
          </div>
          <Field label="City" name="city" required value={v.address.city} onChange={(e) => setAddr("city", e.target.value)} />
          <Field label="State / region" name="state" value={v.address.state ?? ""} onChange={(e) => setAddr("state", e.target.value || null)} />
          <Field label="Postal code" name="postal" value={v.address.postal_code ?? ""} onChange={(e) => setAddr("postal_code", e.target.value || null)} />
          <Field
            label="Country (2-letter code)"
            name="country"
            required
            maxLength={2}
            value={v.address.country}
            onChange={(e) => setAddr("country", e.target.value.toUpperCase())}
          />
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Pin the location (click the map)</Label>
            <LocationPicker lat={v.address.lat} lng={v.address.lng} onChange={(lat, lng) => setV((p) => ({ ...p, address: { ...p.address, lat, lng } }))} />
            <p className="text-xs text-muted-foreground">
              {v.address.lat}, {v.address.lng}. The public map shows only an approximate area.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Amenities</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {amenities.map((a) => (
            <label key={a.code} className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={v.amenities.includes(a.code)}
                onCheckedChange={(c) => set("amenities", c ? [...v.amenities, a.code] : v.amenities.filter((x) => x !== a.code))}
              />
              {a.label}
            </label>
          ))}
        </CardContent>
      </Card>

      <Button type="submit" size="lg" disabled={busy}>
        {submitLabel}
      </Button>
    </form>
  );
}
