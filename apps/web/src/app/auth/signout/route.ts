import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { LOCAL_AUTH, LOCAL_SESSION_COOKIE, localCookieOptions, sameOrigin } from "@/lib/auth/local";

export async function POST(request: NextRequest) {
  if (LOCAL_AUTH) {
    if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid request origin" }, { status: 403 });
    const response = NextResponse.redirect(new URL("/auth/signin", request.nextUrl.origin), 303);
    response.cookies.set(LOCAL_SESSION_COOKIE, "", { ...localCookieOptions(), maxAge: 0 });
    return response;
  }
  const supabase = await createClient();
  await supabase.auth.signOut();
  return NextResponse.redirect(new URL("/auth/signin", request.nextUrl.origin), 303);
}
