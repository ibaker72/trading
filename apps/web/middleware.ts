import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  void request;
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!login|register|landing|api|_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)",
  ],
};
