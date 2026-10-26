"use client";

import { Circle, MapContainer, TileLayer } from "react-leaflet";

// The API only exposes coordinates rounded to ~100 m, and we draw an area
// rather than a pin, like the exact address is only shared after booking.
export default function LocationMapInner({ lat, lng }: { lat: number; lng: number }) {
  return (
    <MapContainer center={[lat, lng]} zoom={14} scrollWheelZoom={false} className="h-80 w-full rounded-xl">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Circle center={[lat, lng]} radius={400} pathOptions={{ color: "#e11d48", fillOpacity: 0.15 }} />
    </MapContainer>
  );
}
