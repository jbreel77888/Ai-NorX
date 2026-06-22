import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

/**
 * Next.js 16 proxy file (replaces deprecated middleware.ts)
 *
 * Public routes: sign-in, sign-up, webhooks
 * Protected routes: everything else requires authentication
 */
const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/webhooks(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  const { userId } = await auth();

  // If signed in and trying to access sign-in/sign-up, redirect to /chat
  if (userId && isPublicRoute(req)) {
    const homeUrl = new URL("/chat", req.url);
    return NextResponse.redirect(homeUrl);
  }

  // If not signed in and trying to access protected route, redirect to /sign-in
  if (!userId && !isPublicRoute(req)) {
    const signInUrl = new URL("/sign-in", req.url);
    return NextResponse.redirect(signInUrl);
  }
});

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico|css|js|woff|woff2|ttf|eot|otf)).*)",
  ],
};
