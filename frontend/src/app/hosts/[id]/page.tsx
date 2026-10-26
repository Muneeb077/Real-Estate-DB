import { ShieldCheckIcon, StarIcon } from "lucide-react";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ListingCard } from "@/components/listing/listing-card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { shortDate } from "@/lib/format";
import { getHost } from "@/lib/listings";

export default function HostPage({ params }: PageProps<"/hosts/[id]">) {
  return (
    <Suspense fallback={<div className="mx-auto h-96 max-w-6xl animate-pulse px-4 py-10" />}>
      {params.then(({ id }) => (
        <HostContent id={id} />
      ))}
    </Suspense>
  );
}

async function HostContent({ id }: { id: string }) {
  const host = await getHost(id);
  if (!host) notFound();
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <Avatar className="size-24">
          <AvatarImage src={host.avatar_url ?? undefined} alt="" />
          <AvatarFallback>{host.name[0]}</AvatarFallback>
        </Avatar>
        <div>
          <h1 className="text-3xl font-semibold">{host.name}</h1>
          {host.agency_name && <p className="text-muted-foreground">{host.agency_name}</p>}
          <div className="mt-2 flex flex-wrap gap-4 text-sm">
            {host.verified && (
              <span className="flex items-center gap-1">
                <ShieldCheckIcon className="size-4 text-emerald-600" /> Verified host
              </span>
            )}
            <span>{host.stats.listings.toLocaleString()} active listings</span>
            {host.stats.rating_avg && (
              <span className="flex items-center gap-1">
                <StarIcon className="size-4 fill-current" /> {host.stats.rating_avg} ({host.stats.reviews} reviews)
              </span>
            )}
            <span>Member since {shortDate(host.member_since)}</span>
          </div>
          {host.bio && <p className="mt-3 max-w-2xl text-muted-foreground">{host.bio}</p>}
        </div>
      </div>
      <h2 className="mt-12 mb-6 text-xl font-semibold">Latest listings</h2>
      <div className="grid gap-x-5 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
        {host.listings.map((l) => (
          <ListingCard key={l.public_id} listing={l} />
        ))}
      </div>
    </div>
  );
}
