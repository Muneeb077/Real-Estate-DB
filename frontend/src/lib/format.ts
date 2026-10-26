import type { ListingMode, PriceUnit } from "./types";

export function money(amount: number, currency = "USD", compact = false) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    // whole amounts and compact figures show no cents; min must never exceed max
    minimumFractionDigits: Number.isInteger(amount) || compact ? 0 : 2,
    maximumFractionDigits: Number.isInteger(amount) || compact ? (compact ? 1 : 0) : 2,
    notation: compact && amount >= 100000 ? "compact" : "standard",
  }).format(amount);
}

export function priceLabel(price: number, unit: PriceUnit, currency = "USD", compact = false) {
  const suffix = unit === "night" ? " night" : unit === "month" ? " month" : "";
  return `${money(price, currency, compact)}${suffix ? ` /${suffix.trim()}` : ""}`;
}

export const MODE_LABEL: Record<ListingMode, string> = {
  sale: "For sale",
  long_term_rent: "Long-term rent",
  short_term_stay: "Stay",
};

export function shortDate(iso: string | null | undefined) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
