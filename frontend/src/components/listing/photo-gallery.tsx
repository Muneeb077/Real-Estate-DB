"use client";

import { GridIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import type { Photo } from "@/lib/types";

import { ListingImage } from "./listing-image";

export function PhotoGallery({ photos, title }: { photos: Photo[]; title: string }) {
  const [open, setOpen] = useState(false);
  const [first, ...rest] = photos;
  return (
    <div className="relative">
      <div className="grid h-[300px] grid-cols-4 grid-rows-2 gap-2 overflow-hidden rounded-2xl sm:h-[440px]">
        <div className="relative col-span-4 row-span-2 sm:col-span-2">
          <ListingImage src={first?.url ?? null} alt={first?.alt ?? title} sizes="(max-width: 640px) 100vw, 50vw" priority />
        </div>
        {rest.slice(0, 4).map((p) => (
          <div key={p.id} className="relative hidden sm:block">
            <ListingImage src={p.url} alt={p.alt ?? title} sizes="25vw" />
          </div>
        ))}
      </div>
      {photos.length > 1 && (
        <Button variant="outline" className="absolute right-4 bottom-4 bg-background" onClick={() => setOpen(true)}>
          <GridIcon /> Show all {photos.length} photos
        </Button>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
          <DialogTitle>{title}</DialogTitle>
          <div className="grid gap-3">
            {photos.map((p) => (
              <div key={p.id} className="relative aspect-[3/2] overflow-hidden rounded-lg">
                <ListingImage src={p.url} alt={p.alt ?? title} sizes="(max-width: 896px) 100vw, 896px" />
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
