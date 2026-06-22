import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

/**
 * Simplified middleware - let Clerk handle auth internally.
 * Clerk will redirect to /sign-in when needed.
 *
 * The 401 issue was because auth() was being awaited unnecessarily
 * and the redirect logic was conflicting with Clerk's built-in protection.
 */
export default clerkMiddleware();

export const config = {
  // Run middleware on all routes except static files
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico|css|js|woff|woff2|ttf|eot|otf)).*)",
  ],
};
