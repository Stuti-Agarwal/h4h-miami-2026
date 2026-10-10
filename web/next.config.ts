import type { NextConfig } from "next";

const flaskUrl = process.env.FLASK_URL ?? "http://localhost:5050";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${flaskUrl}/api/:path*` }];
  },
};

export default nextConfig;
