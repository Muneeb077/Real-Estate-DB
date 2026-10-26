export type ListingMode = "sale" | "long_term_rent" | "short_term_stay";
export type PriceUnit = "total" | "month" | "night";
export type Role = "guest" | "host" | "admin";

export interface ListingCard {
  public_id: string;
  title: string;
  listing_mode: ListingMode;
  property_type: string;
  bedrooms: number;
  bathrooms: number;
  max_guests: number | null;
  size_sqft: number | null;
  price: number;
  currency: string;
  price_unit: PriceUnit;
  city: string;
  state: string | null;
  country: string;
  lat: number;
  lng: number;
  cover_url: string | null;
  cover_thumb_url: string | null;
  rating_avg: number | null;
  review_count: number;
  published_at: string;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Amenity {
  code: string;
  label: string;
  category: string;
}

export interface Photo {
  id: number;
  url: string;
  thumb_url: string | null;
  alt: string | null;
}

export interface Review {
  id: number;
  rating: number;
  comment: string;
  host_reply: string | null;
  created_at: string;
  author: { name: string; avatar_url: string | null };
}

export interface ListingDetail extends ListingCard {
  description: string;
  status: string;
  photos: Photo[];
  amenities: Amenity[];
  host: { public_id: string; name: string; avatar_url: string | null; verified: boolean; member_since: string };
  reviews: Review[];
  views: number;
}

export interface Me {
  public_id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  roles: Role[];
  email_verified: boolean;
}
