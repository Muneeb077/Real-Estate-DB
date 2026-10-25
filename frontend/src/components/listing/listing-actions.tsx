"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useMe } from "@/lib/auth";
import { priceLabel } from "@/lib/format";
import type { ListingDetail } from "@/lib/types";

/**
 * Sticky action panel on the listing page. Browsing is public; acting needs an account.
 */
export function ListingActions({ listing }: { listing: ListingDetail }) {
  const { data: me } = useMe();
  return (
    <Card className="shadow-lg">
      <CardContent className="space-y-4">
        <div className="text-2xl font-semibold">{priceLabel(listing.price, listing.price_unit, listing.currency)}</div>
        {!me && (
          <Button className="w-full" size="lg" render={<Link href={`/login?next=/listings/${listing.public_id}`} />} nativeButton={false}>
            Log in to continue
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
