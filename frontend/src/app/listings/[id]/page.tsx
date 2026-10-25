import { BathIcon, BedDoubleIcon, CheckIcon, RulerIcon, ShieldCheckIcon, StarIcon, UsersIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { FavoriteButton } from "@/components/listing/favorite-button";
import { ListingActions } from "@/components/listing/listing-actions";
import { LocationMap } from "@/components/listing/location-map";
import { PhotoGallery } from "@/components/listing/photo-gallery";
import { ReviewsSection } from "@/components/listing/reviews-section";
import { ViewBeacon } from "@/components/listing/view-beacon";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { MODE_LABEL, shortDate } from "@/lib/format";
import { getListing } from "@/lib/listings";

export async function generateMetadata({ params }: PageProps<"/listings/[id]">): Promise<Metadata> {
  const { id } = await params;
  const listing = await getListing(id);
  if (!listing) return { title: "Listing not found" };
  return {
    title: `${listing.title} · ${listing.city}`,
    description: listing.description.slice(0, 160),
    openGraph: { images: listing.cover_url ? [listing.cover_url] : [] },
  };
}

export default function ListingPage({ params }: PageProps<"/listings/[id]">) {
  return (
    <Suspense fallback={<ListingSkeleton />}>
      {params.then(({ id }) => (
        <ListingContent id={id} />
      ))}
    </Suspense>
  );
}

async function ListingContent({ id }: { id: string }) {
  const listing = await getListing(id);
  if (!listing) notFound();

  const byCategory = Object.groupBy(listing.amenities, (a) => a.category);
  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
      <ViewBeacon publicId={listing.public_id} />
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold sm:text-3xl">{listing.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="secondary">{MODE_LABEL[listing.listing_mode]}</Badge>
            {listing.rating_avg != null && (
              <span className="flex items-center gap-1 text-foreground">
                <StarIcon className="size-3.5 fill-current" /> {listing.rating_avg.toFixed(2)} · {listing.review_count} {listing.review_count === 1 ? "review" : "reviews"}
              </span>
            )}
            <span>
              {listing.city}
              {listing.state ? `, ${listing.state}` : ""}, {listing.country}
            </span>
          </div>
        </div>
        <FavoriteButton publicId={listing.public_id} className="border" />
      </div>

      <PhotoGallery photos={listing.photos} title={listing.title} />

      <div className="mt-8 grid gap-10 lg:grid-cols-[1fr_380px]">
        <div className="min-w-0 space-y-8">
          <section className="flex flex-wrap gap-6 text-sm">
            <span className="flex items-center gap-2 capitalize">
              <BedDoubleIcon className="size-5" /> {listing.bedrooms ? `${listing.bedrooms} bedrooms` : "Studio"}
            </span>
            <span className="flex items-center gap-2">
              <BathIcon className="size-5" /> {listing.bathrooms} baths
            </span>
            {listing.size_sqft && (
              <span className="flex items-center gap-2">
                <RulerIcon className="size-5" /> {listing.size_sqft.toLocaleString()} sqft
              </span>
            )}
            {listing.max_guests && (
              <span className="flex items-center gap-2">
                <UsersIcon className="size-5" /> Up to {listing.max_guests} guests
              </span>
            )}
            <span className="capitalize">{listing.property_type}</span>
          </section>
          <Separator />
          <Link href={`/hosts/${listing.host.public_id}`} className="flex items-center gap-4 rounded-xl hover:bg-muted/50">
            <Avatar className="size-12">
              <AvatarImage src={listing.host.avatar_url ?? undefined} alt="" />
              <AvatarFallback>{listing.host.name[0]}</AvatarFallback>
            </Avatar>
            <div>
              <div className="font-semibold">Listed by {listing.host.name}</div>
              <div className="flex items-center gap-1 text-sm text-muted-foreground">
                {listing.host.verified && <ShieldCheckIcon className="size-4 text-emerald-600" />}
                {listing.host.verified ? "Verified host · " : ""}Member since {shortDate(listing.host.member_since)}
              </div>
            </div>
          </Link>
          <Separator />
          <section>
            <h2 className="mb-3 text-xl font-semibold">About this place</h2>
            <p className="leading-relaxed whitespace-pre-line text-muted-foreground">{listing.description}</p>
          </section>
          <Separator />
          <section>
            <h2 className="mb-4 text-xl font-semibold">What this place offers</h2>
            <div className="grid gap-6 sm:grid-cols-2">
              {Object.entries(byCategory).map(([cat, items]) => (
                <div key={cat}>
                  <div className="mb-2 text-sm font-semibold capitalize">{cat}</div>
                  <ul className="space-y-1.5 text-sm">
                    {items?.map((a) => (
                      <li key={a.code} className="flex items-center gap-2">
                        <CheckIcon className="size-4 text-primary" /> {a.label}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
          <Separator />
          <section>
            <h2 className="mb-1 text-xl font-semibold">Where you&apos;ll be</h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Approximate area. The exact address is shared after a booking or accepted offer.
            </p>
            <LocationMap lat={listing.lat} lng={listing.lng} />
          </section>
          <Separator />
          <ReviewsSection listing={listing} />
        </div>
        <div>
          <div className="lg:sticky lg:top-24">
            <ListingActions listing={listing} />
            <p className="mt-3 text-center text-xs text-muted-foreground">{listing.views.toLocaleString()} views</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function ListingSkeleton() {
  return (
    <div className="mx-auto max-w-6xl animate-pulse px-4 py-6 sm:px-6">
      <div className="h-8 w-2/3 rounded bg-muted" />
      <div className="mt-3 h-4 w-1/3 rounded bg-muted" />
      <div className="mt-6 h-[440px] rounded-2xl bg-muted" />
    </div>
  );
}
