import Image from "next/image";

import { cn } from "cn";

/**
 * Remote seed photos go through next/image; uploads served from /media by the API
 * are already resized to WebP by the worker, so they skip the optimizer.
 */
export function ListingImage({
  src,
  alt,
  className,
  sizes,
  priority,
}: {
  src: string | null;
  alt: string;
  className?: string;
  sizes?: string;
  priority?: boolean;
}) {
  if (!src) return <div className={cn("bg-muted", className)} aria-hidden />;
  return (
    <Image
      src={src}
      alt={alt}
      fill
      sizes={sizes ?? "(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"}
      className={cn("object-cover", className)}
      unoptimized={src.startsWith("/media/")}
      priority={priority}
    />
  );
}
