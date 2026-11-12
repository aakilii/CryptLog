import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"

/**
 * Keep Operation Room URLs at `/cases/...` (matches the standalone app) while the real
 * routes live under `app/operation-room/(main)/cases/...` in this Next.js project.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  if (pathname === "/cases" || pathname.startsWith("/cases/")) {
    const url = request.nextUrl.clone()
    url.pathname = `/operation-room${pathname}`
    return NextResponse.rewrite(url)
  }
  return NextResponse.next()
}

export const config = {
  matcher: ["/cases", "/cases/:path*"],
}
