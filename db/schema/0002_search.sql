-- 0002 public search: helper index for city facets
CREATE INDEX idx_listings_city_mode ON listings (city, listing_mode, status);
