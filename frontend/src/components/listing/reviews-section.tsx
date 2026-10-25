import { StarIcon } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { shortDate } from "@/lib/format";
import type { ListingDetail } from "@/lib/types";

export function ReviewsSection({ listing }: { listing: ListingDetail }) {
  return (
    <section>
      <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold">
        <StarIcon className="size-5 fill-current" />
        {listing.review_count ? `${listing.rating_avg?.toFixed(2)} · ${listing.review_count} reviews` : "No reviews yet"}
      </h2>
      <div className="grid gap-6 sm:grid-cols-2">
        {listing.reviews.map((r) => (
          <article key={r.id} className="space-y-2">
            <div className="flex items-center gap-3">
              <Avatar>
                <AvatarImage src={r.author.avatar_url ?? undefined} alt="" />
                <AvatarFallback>{r.author.name[0]}</AvatarFallback>
              </Avatar>
              <div>
                <div className="font-medium">{r.author.name}</div>
                <div className="text-xs text-muted-foreground">{shortDate(r.created_at)}</div>
              </div>
            </div>
            <div className="flex" aria-label={`${r.rating} out of 5 stars`}>
              {Array.from({ length: 5 }, (_, i) => (
                <StarIcon key={i} className={`size-3.5 ${i < r.rating ? "fill-current" : "text-muted-foreground"}`} />
              ))}
            </div>
            <p className="text-sm text-muted-foreground">{r.comment}</p>
            {r.host_reply && (
              <p className="border-l-2 pl-3 text-sm">
                <span className="font-medium">Host reply: </span>
                {r.host_reply}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
