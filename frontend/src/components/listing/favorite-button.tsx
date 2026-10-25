"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HeartIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { api, errorMessage } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { cn } from "cn";

export function useFavoriteIds() {
  const { data: me } = useMe();
  return useQuery({
    queryKey: ["favorite-ids"],
    queryFn: () => api<string[]>("/me/favorites/ids"),
    enabled: !!me,
    staleTime: 60_000,
  });
}

export function FavoriteButton({ publicId, className }: { publicId: string; className?: string }) {
  const { data: me } = useMe();
  const { data: ids } = useFavoriteIds();
  const qc = useQueryClient();
  const router = useRouter();
  const saved = !!ids?.includes(publicId);

  const toggle = useMutation({
    mutationFn: () => api(`/me/favorites/${publicId}`, { method: saved ? "DELETE" : "PUT" }),
    onMutate: () => {
      qc.setQueryData<string[]>(["favorite-ids"], (old = []) =>
        saved ? old.filter((id) => id !== publicId) : [...old, publicId],
      );
    },
    onError: (e) => {
      toast.error(errorMessage(e));
      qc.invalidateQueries({ queryKey: ["favorite-ids"] });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });

  return (
    <button
      type="button"
      aria-label={saved ? "Remove from wishlist" : "Save to wishlist"}
      aria-pressed={saved}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!me) {
          router.push(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
          return;
        }
        toggle.mutate();
      }}
      className={cn(
        "grid size-9 place-items-center rounded-full bg-background/70 backdrop-blur transition hover:scale-110",
        className,
      )}
    >
      <HeartIcon className={cn("size-5", saved ? "fill-primary text-primary" : "text-foreground")} />
    </button>
  );
}
