"use client";

import dynamic from "next/dynamic";

const Inner = dynamic(() => import("./location-map-inner"), {
  ssr: false,
  loading: () => <div className="h-80 animate-pulse rounded-xl bg-muted" />,
});

export function LocationMap(props: { lat: number; lng: number }) {
  return <Inner {...props} />;
}
