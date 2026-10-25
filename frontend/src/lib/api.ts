"use client";

/**
 * Browser API client. Requests go to /api/v1 on this origin (proxied to Flask by
 * next.config rewrites), so the httpOnly auth cookies ride along automatically.
 * Unsafe methods carry the double-submit CSRF token; an expired access token is
 * refreshed once and the request retried.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: { field: string; message: string }[],
  ) {
    super(message);
  }
}

const BASE = "/api/v1";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function readCookie(name: string) {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${name}=`))
    ?.split("=")[1];
}

async function csrfToken() {
  let token = readCookie("hn_csrf");
  if (!token) {
    await fetch(`${BASE}/auth/csrf`, { credentials: "same-origin" });
    token = readCookie("hn_csrf");
  }
  return token ?? "";
}

let refreshing: Promise<boolean> | null = null;

async function refresh() {
  refreshing ??= (async () => {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRF-Token": await csrfToken() },
    });
    return res.ok;
  })().finally(() => setTimeout(() => (refreshing = null), 0));
  return refreshing;
}

type Options = { method?: string; body?: unknown; form?: FormData; retry?: boolean };

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? (opts.body || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = {};
  if (UNSAFE.has(method)) headers["X-CSRF-Token"] = await csrfToken();
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
  });

  if (res.status === 401 && opts.retry !== false && !path.startsWith("/auth/")) {
    if (await refresh()) return api<T>(path, { ...opts, retry: false });
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = data?.error ?? {};
    throw new ApiError(res.status, e.code ?? "error", e.message ?? res.statusText, e.details);
  }
  return data as T;
}

export function errorMessage(e: unknown) {
  if (e instanceof ApiError) {
    if (e.details?.length) return e.details.map((d) => `${d.field}: ${d.message}`).join("; ");
    return e.message;
  }
  return "Something went wrong.";
}
