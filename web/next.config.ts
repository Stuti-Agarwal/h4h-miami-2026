import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const flaskUrl = process.env.FLASK_URL ?? "http://localhost:5050";

export default function config(phase: string): NextConfig {
  // Dev: proxy /api/* to Flask via a rewrite.
  // Build: static export to out/ for Cloudflare Pages; /api/* is proxied at
  // runtime by functions/api/[[path]].ts (rewrites don't work with export).
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return {
      cacheComponents: true,
      partialPrefetching: true,
      devIndicators: false,
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${flaskUrl}/api/:path*` }];
      },
    };
  }
  return { output: "export", devIndicators: false };
}
