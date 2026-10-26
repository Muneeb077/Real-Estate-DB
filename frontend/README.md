# HomeNest frontend

Next.js 16 (App Router, Cache Components) + React 19 + Tailwind 4 + shadcn/ui (Base UI).

```bash
npm ci
npm run dev        # http://localhost:3000, proxies /api and /media to API_INTERNAL_URL (default http://127.0.0.1:5050)
npm run build && npm start
```

- `src/app`: routes (public: `/`, `/search`, `/listings/[id]`, `/hosts/[id]`; signed-in: `/trips`, `/wishlists`, `/inbox`,
  `/account`; `/host/*`, `/admin/*`)
- `src/lib/api.ts`: browser client (same-origin cookies, CSRF header, silent refresh)
- `src/lib/listings.ts`: cached server-side fetches for public pages (`"use cache"` + `cacheLife`)
- `src/components/map`: Leaflet map, loaded client-side only

See the repository [README](../README.md) for the full picture.
