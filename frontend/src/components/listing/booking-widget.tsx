"use client";

import type { ListingDetail } from "@/lib/types";

export function BookingWidget({ listing }: { listing: ListingDetail }) {
  return <p className="text-sm text-muted-foreground">Up to {listing.max_guests} guests. Online booking is coming soon.</p>;
}
