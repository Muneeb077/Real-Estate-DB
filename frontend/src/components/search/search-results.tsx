"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { ListIcon, MapIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import type { DateRange } from "react-day-picker";

import { ListingCard, ListingCardSkeleton } from "@/components/listing/listing-card";
import { ListingsMap, type Bounds } from "@/components/map";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, errorMessage } from "@/lib/api";
import type { ListingCard as Listing, Page } from "@/lib/types";

import { DateRangePicker, isoDate } from "./date-range-picker";
import { FiltersSheet, NativeSelect, type Filters } from "./filters-sheet";

const KEYS = [
  "q", "mode", "type", "city", "min_price", "max_price", "beds", "baths", "guests", "amenities",
  "bbox", "check_in", "check_out", "sort",
];

export function SearchResults() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const params = useMemo(() => {
    const p: Filters = {};
    for (const k of KEYS) p[k] = sp.get(k) ?? undefined;
    return p;
  }, [sp]);

  const [view, setView] = useState<"list" | "map">("list");
  const [hovered, setHovered] = useState<string | null>(null);
  const [searchOnMove, setSearchOnMove] = useState(true);
  const [city, setCity] = useState(params.city ?? "");

  function update(next: Filters) {
    const merged = { ...params, ...next };
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(merged)) if (v) qs.set(k, v);
    router.replace(`${pathname}?${qs}`, { scroll: false });
  }

  const query = useInfiniteQuery({
    queryKey: ["search", params],
    queryFn: ({ pageParam }) => {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v);
      if (pageParam) qs.set("cursor", pageParam);
      return api<Page<Listing>>(`/listings?${qs}`);
    },
    initialPageParam: "",
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const listings = useMemo(() => query.data?.pages.flatMap((p) => p.items) ?? [], [query.data]);

  // infinite scroll
  const sentinel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && query.hasNextPage && !query.isFetchingNextPage) query.fetchNextPage();
    });
    io.observe(el);
    return () => io.disconnect();
  }, [query]);

  const dates: DateRange | undefined = params.check_in
    ? { from: new Date(`${params.check_in}T00:00`), to: params.check_out ? new Date(`${params.check_out}T00:00`) : undefined }
    : undefined;
  const isStay = params.mode === "short_term_stay";

  return (
    <div className="mx-auto max-w-[1600px] px-4 sm:px-6">
      <div className="sticky top-16 z-30 -mx-4 flex flex-wrap items-center gap-2 border-b bg-background/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <Tabs value={params.mode ?? "all"} onValueChange={(v) => update({ mode: v === "all" ? undefined : String(v) })}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="short_term_stay">Stays</TabsTrigger>
            <TabsTrigger value="long_term_rent">Rent</TabsTrigger>
            <TabsTrigger value="sale">Buy</TabsTrigger>
          </TabsList>
        </Tabs>
        <form
          className="flex"
          onSubmit={(e) => {
            e.preventDefault();
            update({ city: city.trim() || undefined, bbox: undefined });
          }}
        >
          <Input aria-label="City" className="w-40" placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
        </form>
        {isStay && (
          <div className="w-56">
            <DateRangePicker
              className="h-9"
              value={dates}
              onChange={(r) => {
                if (r?.from && r?.to) update({ check_in: isoDate(r.from), check_out: isoDate(r.to) });
                else if (!r) update({ check_in: undefined, check_out: undefined });
              }}
            />
          </div>
        )}
        <FiltersSheet value={params} onApply={(f) => update(f)} />
        <div className="w-40">
          <NativeSelect aria-label="Sort" value={params.sort ?? "newest"} onChange={(e) => update({ sort: e.target.value })}>
            <option value="newest">Newest</option>
            <option value="price_asc">Price: low to high</option>
            <option value="price_desc">Price: high to low</option>
            <option value="rating">Top rated</option>
          </NativeSelect>
        </div>
        {params.bbox && (
          <Button variant="ghost" size="sm" onClick={() => update({ bbox: undefined })}>
            Clear map area
          </Button>
        )}
        <Button className="ml-auto lg:hidden" variant="outline" onClick={() => setView(view === "list" ? "map" : "list")}>
          {view === "list" ? <MapIcon /> : <ListIcon />} {view === "list" ? "Map" : "List"}
        </Button>
      </div>

      <div className="grid gap-6 pt-4 lg:grid-cols-[minmax(0,1fr)_42%]">
        <section className={view === "map" ? "hidden lg:block" : ""} aria-live="polite">
          {query.isError ? (
            <p className="py-16 text-center text-destructive">{errorMessage(query.error)}</p>
          ) : query.isLoading ? (
            <div className="grid gap-x-5 gap-y-8 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 9 }, (_, i) => (
                <ListingCardSkeleton key={i} />
              ))}
            </div>
          ) : listings.length === 0 ? (
            <div className="py-24 text-center">
              <p className="text-lg font-semibold">No exact matches</p>
              <p className="text-muted-foreground">Try removing filters or zooming out on the map.</p>
            </div>
          ) : (
            <div className="grid gap-x-5 gap-y-8 sm:grid-cols-2 xl:grid-cols-3">
              {listings.map((l, i) => (
                <ListingCard key={l.public_id} listing={l} onHover={setHovered} priority={i < 3} />
              ))}
              {query.isFetchingNextPage &&
                Array.from({ length: 3 }, (_, i) => <ListingCardSkeleton key={`more-${i}`} />)}
            </div>
          )}
          <div ref={sentinel} className="h-10" />
        </section>

        <aside className={`${view === "list" ? "hidden lg:block" : ""} lg:sticky lg:top-36 lg:h-[calc(100vh-10rem)]`}>
          <div className="relative h-[70vh] overflow-hidden rounded-xl border lg:h-full">
            <ListingsMap
              listings={listings}
              fitKey={`${params.mode}|${params.city}|${params.q}|${params.type}`}
              activeId={hovered}
              fitOnLoad={!params.bbox}
              onMove={searchOnMove ? (b: Bounds) => update({ bbox: b.join(","), city: undefined }) : undefined}
            />
            <label className="absolute top-3 left-1/2 z-[500] flex -translate-x-1/2 items-center gap-2 rounded-full bg-background px-3 py-1.5 text-sm shadow">
              <Switch checked={searchOnMove} onCheckedChange={setSearchOnMove} /> Search as I move the map
            </label>
          </div>
        </aside>
      </div>
    </div>
  );
}
