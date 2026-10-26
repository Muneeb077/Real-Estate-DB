import { StarIcon } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { MODE_LABEL, priceLabel } from "@/lib/format";
import type { ListingCard as Listing } from "@/lib/types";

import { FavoriteButton } from "./favorite-button";
import { ListingImage } from "./listing-image";

export function ListingCard({
  listing,
  onHover,
  priority,
}: {
  listing: Listing;
  onHover?: (id: string | null) => void;
  priority?: boolean;
}) {
  return (
    <Link
      href={`/listings/${listing.public_id}`}
      className="group block"
      onMouseEnter={onHover ? () => onHover(listing.public_id) : undefined}
      onMouseLeave={onHover ? () => onHover(null) : undefined}
    >
      <div className="relative aspect-[4/3] overflow-hidden rounded-xl bg-muted">
        <ListingImage
          src={listing.cover_thumb_url ?? listing.cover_url}
          alt={listing.title}
          className="transition duration-300 group-hover:scale-105"
          priority={priority}
        />
        <Badge variant="secondary" className="absolute top-3 left-3 bg-background/85 backdrop-blur">
          {MODE_LABEL[listing.listing_mode]}
        </Badge>
        <FavoriteButton publicId={listing.public_id} className="absolute top-2 right-2" />
      </div>
      <div className="mt-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate font-semibold">
            {listing.city}, {listing.country}
          </div>
          <div className="truncate text-sm text-muted-foreground">{listing.title}</div>
          <div className="text-sm text-muted-foreground">
            {listing.bedrooms ? `${listing.bedrooms} bed` : "Studio"} · {listing.bathrooms} bath
            {listing.size_sqft ? ` · ${listing.size_sqft.toLocaleString()} sqft` : ""}
          </div>
        </div>
        {listing.rating_avg != null && (
          <div className="flex shrink-0 items-center gap-1 text-sm">
            <StarIcon className="size-3.5 fill-current" />
            {listing.rating_avg.toFixed(2)}
          </div>
        )}
      </div>
      <div className="mt-1 font-semibold">{priceLabel(listing.price, listing.price_unit, listing.currency)}</div>
    </Link>
  );
}

export function ListingCardSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="aspect-[4/3] rounded-xl bg-muted" />
      <div className="mt-3 h-4 w-2/3 rounded bg-muted" />
      <div className="mt-2 h-3 w-1/2 rounded bg-muted" />
      <div className="mt-2 h-4 w-1/4 rounded bg-muted" />
    </div>
  );
}
