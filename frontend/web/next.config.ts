import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  // SSE through the proxy must not be gzip-buffered (ADR-010 §4.3).
  compress: false,
  experimental: {
    // Above core-api's 20 MB upload limit; the default 10 MB cuts larger multipart bodies.
    proxyClientMaxBodySize: '25mb',
    // Idle-socket limit of the proxied request (Next default 30 s). Raised to 10 min to tolerate
    // Modal GPU cold starts; SSE sends a ping every 15 s once streaming begins.
    proxyTimeout: 600_000,
  },
};

export default nextConfig;
