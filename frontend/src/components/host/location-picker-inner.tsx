"use client";

import { CircleMarker, MapContainer, TileLayer, useMapEvents } from "react-leaflet";

function Clicks({ onChange }: { onChange: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (e) => onChange(+e.latlng.lat.toFixed(6), +e.latlng.lng.toFixed(6)) });
  return null;
}

export default function LocationPickerInner({ lat, lng, onChange }: { lat: number; lng: number; onChange: (lat: number, lng: number) => void }) {
  return (
    <MapContainer center={[lat, lng]} zoom={13} className="h-72 w-full rounded-xl">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Clicks onChange={onChange} />
      <CircleMarker center={[lat, lng]} radius={8} pathOptions={{ color: "#fff", weight: 2, fillColor: "#e11d48", fillOpacity: 1 }} />
    </MapContainer>
  );
}
