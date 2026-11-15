import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  // SSE through the proxy must not be gzip-buffered (ADR-010 §4.3).
  compress: false,
  experimental: {
    // Above core-api's 20 MB upload limit; the default 10 MB cuts larger multipart bodies.
    proxyClientMaxBodySize: '25mb',
    // Idle-socket limit of the proxied request (Next default 30 s). SSE sends a ping every 15 s.
    proxyTimeout: 120_000,
  },
};

export default nextConfig;
