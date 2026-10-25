import "server-only";

/**
 * Server-side fetch to the Flask API for public, cacheable data (no cookies).
 */
const API_ORIGIN = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:5000";

export async function serverApi<T>(path: string): Promise<T | null> {
  const res = await fetch(`${API_ORIGIN}/api/v1${path}`, { headers: { Accept: "application/json" } });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${path} failed with ${res.status}`);
  return (await res.json()) as T;
}
