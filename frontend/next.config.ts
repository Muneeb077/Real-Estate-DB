import type { NextConfig } from "next";

// The browser only ever talks to this origin: /api and /media are proxied to Flask,
// so auth cookies are first-party and SameSite works without CORS.
const API_ORIGIN = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:5000";

const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self)" },
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  output: "standalone",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  images: {
    remotePatterns: [
      new URL("https://picsum.photos/**"),
      new URL("https://fastly.picsum.photos/**"),
      new URL("https://i.pravatar.cc/**"),
    ],
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` },
      { source: "/media/:path*", destination: `${API_ORIGIN}/media/:path*` },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
