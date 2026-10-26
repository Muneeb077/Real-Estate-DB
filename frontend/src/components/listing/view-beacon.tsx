"use client";

import { useEffect } from "react";

import { api } from "@/lib/api";

export function ViewBeacon({ publicId }: { publicId: string }) {
  useEffect(() => {
    const key = `viewed:${publicId}`;
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, "1");
    api(`/listings/${publicId}/views`, { method: "POST" }).catch(() => undefined);
  }, [publicId]);
  return null;
}
