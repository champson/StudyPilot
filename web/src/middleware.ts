import { NextRequest, NextResponse } from "next/server";

// --- Public routes (no auth required) ---
const PUBLIC_ROUTES = ["/login", "/share"];

// --- Role-specific route patterns ---
const ADMIN_ROUTES = /^\/admin(\/|$)/;
const PARENT_ROUTES = /^\/parent(\/|$)/;

// --- JWT Payload type ---
interface JWTPayload {
  sub: string;
  role: "student" | "parent" | "admin";
  exp: number;
  iat?: number;
}

/**
 * Decode JWT payload without signature verification.
 * Signature verification is done by the backend.
 * Edge Runtime compatible (no Node.js crypto modules).
 */
function decodeJWTPayload(token: string): JWTPayload | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    // Base64URL decode the payload (second part)
    const payload = parts[1];
    // Convert Base64URL to Base64
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    // Pad with = if needed
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);

    // Decode using atob (available in Edge Runtime)
    const decoded = atob(padded);
    return JSON.parse(decoded) as JWTPayload;
  } catch {
    return null;
  }
}

/**
 * Check if the route is public (no auth required)
 */
function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );
}

/**
 * Check if user role has access to the requested route
 */
function hasRouteAccess(pathname: string, role: string): boolean {
  // Admin routes: only admin
  if (ADMIN_ROUTES.test(pathname)) {
    return role === "admin";
  }

  // Parent routes: only parent
  if (PARENT_ROUTES.test(pathname)) {
    return role === "parent";
  }

  // Student routes: only student (not parent)
  return role === "student";
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip public routes
  if (isPublicRoute(pathname)) {
    return NextResponse.next();
  }

  // Get token from cookie
  const token = request.cookies.get("access_token")?.value;

  // No token -> redirect to login
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Decode JWT payload for role check
  const payload = decodeJWTPayload(token);

  // Invalid token -> redirect to login
  if (!payload) {
    const response = NextResponse.redirect(new URL("/login", request.url));
    // Clear invalid cookie
    response.cookies.delete("access_token");
    return response;
  }

  // Check token expiration (client-side check, backend will also verify)
  const now = Math.floor(Date.now() / 1000);
  if (payload.exp < now) {
    const response = NextResponse.redirect(new URL("/login", request.url));
    // Clear expired cookie
    response.cookies.delete("access_token");
    return response;
  }

  // Check role-based access
  if (!hasRouteAccess(pathname, payload.role)) {
    // Redirect to appropriate home page based on role
    const redirectUrl =
      payload.role === "admin"
        ? "/admin"
        : payload.role === "parent"
          ? "/parent"
          : "/dashboard";
    return NextResponse.redirect(new URL(redirectUrl, request.url));
  }

  return NextResponse.next();
}

// --- Matcher configuration ---
// Exclude static files, API routes, and Next.js internals
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt (static meta files)
     * - public folder files (images, etc.)
     * - api routes (handled separately)
     */
    "/((?!_next/static|_next/image|favicon\\.ico|sitemap\\.xml|robots\\.txt|api|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
