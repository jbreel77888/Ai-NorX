import { clerkMiddleware } from "@clerk/nextjs/server";

/**
 * Next.js 16 "proxy" file (replaces deprecated middleware.ts)
 * Clerk handles auth redirects automatically.
 */
export default clerkMiddleware();

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico|css|js|woff|woff2|ttf|eot|otf)).*)",
  ],
};
