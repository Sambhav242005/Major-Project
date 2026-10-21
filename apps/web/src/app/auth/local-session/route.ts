import { NextResponse, type NextRequest } from "next/server";
import { LOCAL_AUTH, LOCAL_SESSION_COOKIE, localCookieOptions, sameOrigin } from "@/lib/auth/local";
import { validatedLocalSession } from "@/lib/auth/local-server";

export async function GET(request: NextRequest) {
  if (!LOCAL_AUTH) return NextResponse.json({ error: "Not found" }, { status: 404 });
  let session;
  try {
    session = await validatedLocalSession(request.cookies.get(LOCAL_SESSION_COOKIE)?.value);
  } catch {
    return NextResponse.json({ error: "The sign-in service is temporarily unavailable. Please try again." }, {
      status: 503, headers: { "Cache-Control": "no-store", "Retry-After": "30" },
    });
  }
  const response = NextResponse.json({ session }, { headers: { "Cache-Control": "no-store" } });
  if (!session) response.cookies.set(LOCAL_SESSION_COOKIE, "", { ...localCookieOptions(), maxAge: 0 });
  return response;
}

export async function DELETE(request: NextRequest) {
  if (!LOCAL_AUTH) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid request origin" }, { status: 403 });
  const response = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  response.cookies.set(LOCAL_SESSION_COOKIE, "", { ...localCookieOptions(), maxAge: 0 });
  return response;
}
