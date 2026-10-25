"use client";

import { SearchIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { DateRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ListingMode } from "@/lib/types";

import { DateRangePicker, isoDate } from "./date-range-picker";

export function SearchBar({ initialMode = "short_term_stay" }: { initialMode?: ListingMode }) {
  const router = useRouter();
  const [mode, setMode] = useState<ListingMode>(initialMode);
  const [city, setCity] = useState("");
  const [q, setQ] = useState("");
  const [dates, setDates] = useState<DateRange | undefined>();
  const [guests, setGuests] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams({ mode });
    if (city.trim()) params.set("city", city.trim());
    if (q.trim()) params.set("q", q.trim());
    if (mode === "short_term_stay") {
      if (dates?.from && dates?.to) {
        params.set("check_in", isoDate(dates.from)!);
        params.set("check_out", isoDate(dates.to)!);
      }
      if (guests) params.set("guests", guests);
    }
    router.push(`/search?${params}`);
  }

  return (
    <form onSubmit={submit} className="rounded-2xl border bg-card p-3 shadow-lg sm:p-4">
      <Tabs value={mode} onValueChange={(v) => setMode(v as ListingMode)}>
        <TabsList className="mb-3">
          <TabsTrigger value="short_term_stay">Stays</TabsTrigger>
          <TabsTrigger value="long_term_rent">Rent</TabsTrigger>
          <TabsTrigger value="sale">Buy</TabsTrigger>
        </TabsList>
      </Tabs>
      <div className="grid gap-2 md:grid-cols-[1.2fr_1fr_1.2fr_0.6fr_auto]">
        <label className="sr-only" htmlFor="sb-city">
          City
        </label>
        <Input
          id="sb-city"
          className="h-11"
          placeholder="Where? e.g. Lisbon"
          value={city}
          onChange={(e) => setCity(e.target.value)}
        />
        <label className="sr-only" htmlFor="sb-q">
          Keywords
        </label>
        <Input id="sb-q" className="h-11" placeholder="Keywords: garden, view…" value={q} onChange={(e) => setQ(e.target.value)} />
        {mode === "short_term_stay" ? (
          <>
            <DateRangePicker value={dates} onChange={setDates} />
            <Input
              aria-label="Guests"
              className="h-11"
              type="number"
              min={1}
              max={16}
              placeholder="Guests"
              value={guests}
              onChange={(e) => setGuests(e.target.value)}
            />
          </>
        ) : (
          <div className="hidden md:col-span-2 md:block" />
        )}
        <Button type="submit" size="lg" className="h-11 px-6">
          <SearchIcon /> Search
        </Button>
      </div>
    </form>
  );
}
