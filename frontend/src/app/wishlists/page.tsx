"use client";

import { useQuery } from "@tanstack/react-query";
import { HeartIcon } from "lucide-react";
import Link from "next/link";

import { PageTitle, RequireAuth } from "@/components/auth/require-auth";
import { ListingCard, ListingCardSkeleton } from "@/components/listing/listing-card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ListingCard as Listing } from "@/lib/types";

export default function WishlistsPage() {
  return <RequireAuth>{() => <Wishlist />}</RequireAuth>;
}

function Wishlist() {
  const { data, isLoading } = useQuery({ queryKey: ["favorites"], queryFn: () => api<Listing[]>("/me/favorites") });
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <PageTitle title="Wishlist" description="Homes you've saved. Unavailable listings drop off automatically." />
      {isLoading ? (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <ListingCardSkeleton key={i} />
          ))}
        </div>
      ) : data?.length ? (
        <div className="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
          {data.map((l) => (
            <ListingCard key={l.public_id} listing={l} />
          ))}
        </div>
      ) : (
        <div className="py-20 text-center">
          <HeartIcon className="mx-auto size-10 text-muted-foreground" />
          <p className="mt-3 font-medium">Nothing saved yet</p>
          <p className="text-muted-foreground">Tap the heart on any listing to save it here.</p>
          <Button className="mt-6" render={<Link href="/search" />} nativeButton={false}>
            Start searching
          </Button>
        </div>
      )}
    </div>
  );
}
