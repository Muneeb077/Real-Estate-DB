"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { api, ApiError } from "./api";
import type { Me, Role } from "./types";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api<Me>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          // access token may have expired: try a silent refresh once
          try {
            await api("/auth/refresh", { method: "POST" });
            return await api<Me>("/auth/me");
          } catch {
            return null;
          }
        }
        throw e;
      }
    },
    staleTime: 60_000,
  });
}

export function hasRole(me: Me | null | undefined, role: Role) {
  return !!me?.roles.includes(role);
}

export function useLogout() {
  const qc = useQueryClient();
  const router = useRouter();
  return async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    qc.clear();
    qc.setQueryData(["me"], null);
    router.push("/");
    router.refresh();
  };
}
