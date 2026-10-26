import "server-only";

import { cacheLife, cacheTag } from "next/cache";

import { serverApi } from "./server-api";
import type { ListingCard, ListingDetail, Page } from "./types";

export async function getListing(id: string) {
  "use cache";
  cacheLife("minutes");
  cacheTag(`listing:${id}`);
  return serverApi<ListingDetail>(`/listings/${encodeURIComponent(id)}`);
}

export async function getHost(id: string) {
  "use cache";
  cacheLife("minutes");
  return serverApi<HostProfile>(`/hosts/${encodeURIComponent(id)}`);
}

export async function getListings(query: string) {
  "use cache";
  cacheLife("minutes");
  return (await serverApi<Page<ListingCard>>(`/listings?${query}`))?.items ?? [];
}

export async function getDestinations() {
  "use cache";
  cacheLife("hours");
  return (await serverApi<Destination[]>("/destinations")) ?? [];
}

export interface Destination {
  city: string;
  country: string;
  listing_mode: string;
  listings: number;
  avg_price: number;
  image: string | null;
}

export interface HostProfile {
  public_id: string;
  name: string;
  avatar_url: string | null;
  bio: string | null;
  agency_name: string | null;
  verified: boolean;
  member_since: string;
  stats: { listings: number; rating_avg: number | null; reviews: number | null };
  listings: ListingCard[];
}
