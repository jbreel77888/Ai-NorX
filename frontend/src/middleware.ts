import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/webhooks(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) {
    await auth.protect({
      // Redirect to /sign-in instead of 401
      signInUrl: "/sign-in",
      signInFallbackRedirectUrl: "/chat",
    });
  }
});

export const config = {
  // Match all paths EXCEPT static files and Next internals
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|gif|webp|svg|ico|css|js|woff|woff2|ttf|eot|otf)).*)",
  ],
};
