import type { Metadata } from "next";
import { Suspense } from "react";

import { ListingCardSkeleton } from "@/components/listing/listing-card";
import { SearchResults } from "@/components/search/search-results";

export const metadata: Metadata = { title: "Search" };

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto grid max-w-7xl gap-6 px-4 py-20 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <ListingCardSkeleton key={i} />
          ))}
        </div>
      }
    >
      <SearchResults />
    </Suspense>
  );
}
