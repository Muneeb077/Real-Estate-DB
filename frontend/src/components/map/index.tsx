"use client";

import dynamic from "next/dynamic";

// Leaflet touches `window` at import time, so the map only renders in the browser.
export const ListingsMap = dynamic(() => import("./listings-map"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse rounded-xl bg-muted" />,
});
export type { Bounds } from "./listings-map";
