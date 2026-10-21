import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { LOCAL_AUTH, LOCAL_SESSION_COOKIE, localCookieOptions } from "@/lib/auth/local";
import { validatedLocalSession } from "@/lib/auth/local-server";

const MOCK_AUTH = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  if (LOCAL_AUTH) {
    const path = request.nextUrl.pathname;
    if (path === "/" || ["/auth", "/contact", "/terms", "/demo"].some((prefix) => path === prefix || path.startsWith(`${prefix}/`))) return supabaseResponse;
    let session;
    try {
      session = await validatedLocalSession(request.cookies.get(LOCAL_SESSION_COOKIE)?.value);
    } catch {
      return new NextResponse("The sign-in service is temporarily unavailable. Please reload shortly.", {
        status: 503, headers: { "Cache-Control": "no-store", "Retry-After": "30" },
      });
    }
    if (session) return supabaseResponse;
    const url = request.nextUrl.clone();
    url.pathname = "/auth/signin";
    const response = NextResponse.redirect(url);
    response.cookies.set(LOCAL_SESSION_COOKIE, "", { ...localCookieOptions(), maxAge: 0 });
    return response;
  }

  // Mock auth mode — skip Supabase entirely
  if (MOCK_AUTH) {
    // Check if user has mock session cookie
    const hasMockSession = request.cookies.get("mock-session")?.value;

    if (
      !hasMockSession &&
      !request.nextUrl.pathname.startsWith("/auth") &&
      !request.nextUrl.pathname.startsWith("/contact") &&
      !request.nextUrl.pathname.startsWith("/terms") &&
      !request.nextUrl.pathname.startsWith("/demo") &&
      request.nextUrl.pathname !== "/"
    ) {
      const url = request.nextUrl.clone();
      url.pathname = "/auth/signin";
      return NextResponse.redirect(url);
    }

    return supabaseResponse;
  }

  // Real Supabase auth
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options?: Record<string, unknown> }[]) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options as Parameters<typeof supabaseResponse.cookies.set>[2])
          );
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Redirect unauthenticated users away from protected routes
  if (
    !user &&
    !request.nextUrl.pathname.startsWith("/auth") &&
    !request.nextUrl.pathname.startsWith("/contact") &&
    !request.nextUrl.pathname.startsWith("/terms") &&
    !request.nextUrl.pathname.startsWith("/demo") &&
    request.nextUrl.pathname !== "/"
  ) {
    const url = request.nextUrl.clone();
    url.pathname = "/auth/signin";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
