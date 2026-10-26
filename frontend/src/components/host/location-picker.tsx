"use client";

import dynamic from "next/dynamic";

const Inner = dynamic(() => import("./location-picker-inner"), {
  ssr: false,
  loading: () => <div className="h-72 animate-pulse rounded-xl bg-muted" />,
});

export function LocationPicker(props: { lat: number; lng: number; onChange: (lat: number, lng: number) => void }) {
  return <Inner {...props} />;
}
