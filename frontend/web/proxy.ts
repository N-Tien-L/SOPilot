import { NextResponse, type NextRequest } from 'next/server';
import { resolveProxyTarget } from '@/lib/server/proxy-target';

// Same-origin proxy to core-api (/api/v1) and ai-service (/ai/v1). A proxy rewrite is used
// instead of next.config rewrites() because the targets must follow run-time env (ADR-010 §4.3).
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const target = resolveProxyTarget(pathname, search, {
    CORE_API_URL: process.env.CORE_API_URL,
    AI_SERVICE_URL: process.env.AI_SERVICE_URL,
  });
  if (!target) return NextResponse.next();
  return NextResponse.rewrite(new URL(target));
}

export const config = {
  matcher: ['/api/v1/:path*', '/ai/v1/:path*'],
};
