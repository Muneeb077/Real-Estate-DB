import { ArrowRightIcon, LockIcon, MapIcon, ShieldCheckIcon } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { ListingCard, ListingCardSkeleton } from "@/components/listing/listing-card";
import { SearchBar } from "@/components/search/search-bar";
import { money } from "@/lib/format";
import { getDestinations, getListings } from "@/lib/listings";

export default function HomePage() {
  return (
    <>
      <section className="relative isolate overflow-hidden">
        <Image
          src="https://picsum.photos/seed/homenest-hero/1920/900"
          alt=""
          fill
          priority
          sizes="100vw"
          className="-z-10 object-cover brightness-[0.55]"
        />
        <div className="mx-auto max-w-6xl px-4 pt-24 pb-20 sm:px-6 sm:pt-32">
          <h1 className="max-w-2xl text-4xl font-bold tracking-tight text-white sm:text-6xl">
            Buy, rent or stay. Find your next place.
          </h1>
          <p className="mt-4 max-w-xl text-lg text-white/85">
            50,000 homes in 34 cities. Browse freely, with no account needed.
          </p>
          <div className="mt-10 max-w-5xl">
            <SearchBar />
          </div>
        </div>
      </section>

      <Section title="Popular destinations for stays" href="/search?mode=short_term_stay">
        <Suspense fallback={<RowSkeleton />}>
          <Destinations />
        </Suspense>
      </Section>
      <Section title="Top-rated stays" href="/search?mode=short_term_stay&sort=rating">
        <Suspense fallback={<RowSkeleton />}>
          <ListingRow query="mode=short_term_stay&sort=rating&limit=8" />
        </Suspense>
      </Section>
      <Section title="New homes for sale" href="/search?mode=sale">
        <Suspense fallback={<RowSkeleton />}>
          <ListingRow query="mode=sale&sort=newest&limit=8" />
        </Suspense>
      </Section>
      <Section title="Long-term rentals" href="/search?mode=long_term_rent">
        <Suspense fallback={<RowSkeleton />}>
          <ListingRow query="mode=long_term_rent&sort=newest&limit=8" />
        </Suspense>
      </Section>

      <section className="mx-auto mt-16 grid max-w-7xl gap-6 px-4 sm:grid-cols-3 sm:px-6">
        {[
          { icon: MapIcon, title: "Search the map", text: "Full-text, radius and map-area search over MySQL spatial indexes." },
          { icon: LockIcon, title: "Private by design", text: "Contact details and exact addresses are encrypted at rest with AES-256-GCM." },
          { icon: ShieldCheckIcon, title: "Verified hosts", text: "Hosts are verified and listings are moderated before going live." },
        ].map(({ icon: Icon, title, text }) => (
          <div key={title} className="rounded-2xl border p-6">
            <Icon className="size-6 text-primary" />
            <div className="mt-3 font-semibold">{title}</div>
            <p className="mt-1 text-sm text-muted-foreground">{text}</p>
          </div>
        ))}
      </section>
    </>
  );
}

function Section({ title, href, children }: { title: string; href: string; children: React.ReactNode }) {
  return (
    <section className="mx-auto mt-14 max-w-7xl px-4 sm:px-6">
      <div className="mb-5 flex items-end justify-between">
        <h2 className="text-2xl font-semibold">{title}</h2>
        <Link href={href} className="flex items-center gap-1 text-sm font-medium hover:underline">
          Show all <ArrowRightIcon className="size-4" />
        </Link>
      </div>
      {children}
    </section>
  );
}

function RowSkeleton() {
  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }, (_, i) => (
        <ListingCardSkeleton key={i} />
      ))}
    </div>
  );
}

async function ListingRow({ query }: { query: string }) {
  await connection(); // fetched at request time (cached briefly), never at build time
  const listings = await getListings(query);
  return (
    <div className="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
      {listings.map((l) => (
        <ListingCard key={l.public_id} listing={l} />
      ))}
    </div>
  );
}

async function Destinations() {
  await connection();
  const all = await getDestinations();
  const stays = all.filter((d) => d.listing_mode === "short_term_stay");
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {stays.map((d) => (
        <Link
          key={d.city}
          href={`/search?mode=short_term_stay&city=${encodeURIComponent(d.city)}`}
          className="group relative aspect-[4/3] overflow-hidden rounded-xl"
        >
          {d.image && (
            <Image src={d.image} alt="" fill sizes="25vw" className="object-cover transition group-hover:scale-105" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent" />
          <div className="absolute bottom-3 left-3 text-white">
            <div className="font-semibold">{d.city}</div>
            <div className="text-xs text-white/80">
              {d.listings.toLocaleString()} stays · avg {money(d.avg_price)}/night
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
