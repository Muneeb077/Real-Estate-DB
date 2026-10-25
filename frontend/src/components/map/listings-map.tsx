"use client";

import L from "leaflet";
import { useEffect, useMemo, useRef } from "react";
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from "react-leaflet";

import { priceLabel } from "@/lib/format";
import type { ListingCard } from "@/lib/types";

export type Bounds = [number, number, number, number]; // min_lat, min_lng, max_lat, max_lng

function pin(label: string, active: boolean) {
  return L.divIcon({
    className: "",
    html: `<div class="price-pin${active ? " active" : ""}">${label}</div>`,
    iconSize: [0, 0],
  });
}

// Refits whenever fitKey changes (new mode/city), not on every page of results.
function FitToResults({
  listings,
  enabled,
  fitKey,
  programmatic,
}: {
  listings: ListingCard[];
  enabled: boolean;
  fitKey: string;
  programmatic: React.RefObject<boolean>;
}) {
  const map = useMap();
  const fittedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!enabled || fittedFor.current === fitKey || listings.length === 0) return;
    programmatic.current = true;
    map.fitBounds(L.latLngBounds(listings.map((l) => [l.lat, l.lng] as [number, number])), { padding: [40, 40] });
    fittedFor.current = fitKey;
  }, [enabled, fitKey, listings, map, programmatic]);
  return null;
}

function BoundsWatcher({ onMove, programmatic }: { onMove?: (b: Bounds) => void; programmatic: React.RefObject<boolean> }) {
  useMapEvents({
    moveend(e) {
      // moves we caused (fitting results) must not trigger a new search
      if (programmatic.current) {
        programmatic.current = false;
        return;
      }
      if (!onMove) return;
      const b = e.target.getBounds();
      onMove([b.getSouth(), b.getWest(), b.getNorth(), b.getEast()].map((n) => +n.toFixed(4)) as Bounds);
    },
  });
  return null;
}

export default function ListingsMap({
  listings,
  activeId,
  onMove,
  fitOnLoad = true,
  fitKey = "",
  center,
  zoom = 12,
  className = "h-full w-full",
}: {
  listings: ListingCard[];
  activeId?: string | null;
  onMove?: (b: Bounds) => void;
  fitOnLoad?: boolean;
  fitKey?: string;
  center?: [number, number];
  zoom?: number;
  className?: string;
}) {
  const start = useMemo<[number, number]>(
    () => center ?? (listings[0] ? [listings[0].lat, listings[0].lng] : [40.7128, -74.006]),
    // initial center only
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  const programmatic = useRef(false);
  return (
    <MapContainer center={start} zoom={zoom} scrollWheelZoom className={className}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitToResults listings={listings} enabled={fitOnLoad} fitKey={fitKey} programmatic={programmatic} />
      <BoundsWatcher onMove={onMove} programmatic={programmatic} />
      {listings.map((l) => (
        <Marker
          key={l.public_id}
          position={[l.lat, l.lng]}
          icon={pin(priceLabel(l.price, l.price_unit, l.currency, true).replace(" /", "/"), l.public_id === activeId)}
          zIndexOffset={l.public_id === activeId ? 1000 : 0}
          eventHandlers={{ click: () => window.open(`/listings/${l.public_id}`, "_self") }}
        />
      ))}
    </MapContainer>
  );
}
