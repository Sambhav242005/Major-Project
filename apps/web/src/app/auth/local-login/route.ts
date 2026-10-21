import { NextResponse, type NextRequest } from "next/server";
import { LOCAL_AUTH, LOCAL_SESSION_COOKIE, localCookieOptions, sameOrigin } from "@/lib/auth/local";
import { internalApiUrl } from "@/lib/auth/local-server";

export async function POST(request: NextRequest) {
  if (!LOCAL_AUTH) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (!sameOrigin(request)) return NextResponse.json({ error: "Invalid request origin" }, { status: 403 });
  let credentials;
  try {
    credentials = await request.json();
    if (typeof credentials.email !== "string" || typeof credentials.password !== "string") throw new Error();
  } catch {
    return NextResponse.json({ error: "Email and password are required" }, { status: 400 });
  }
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    // The private gateway overwrites this IP header. Never relay a browser's
    // claimed proxy secret; only the server runtime can authenticate the hop.
    const clientIp = request.headers.get("x-akgb-client-ip");
    if (process.env.AUTH_PROXY_SECRET && clientIp) {
      headers["X-AKGB-Client-IP"] = clientIp;
      headers["X-AKGB-Proxy-Secret"] = process.env.AUTH_PROXY_SECRET;
    }
    const upstream = await fetch(internalApiUrl("/auth/local-login"), {
      method: "POST", headers,
      body: JSON.stringify({ email: credentials.email, password: credentials.password }),
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    if (upstream.status >= 500) return NextResponse.json({ error: "Sign-in service unavailable" }, { status: 503 });
    if (!upstream.ok) return NextResponse.json({ error: upstream.status === 429 ? "Too many attempts. Please try later." : "Invalid email or password" }, { status: upstream.status === 429 ? 429 : 401 });
    const { session } = await upstream.json();
    if (!session?.access_token || !Number.isFinite(session.expires_in) || session.expires_in <= 0) throw new Error();
    const response = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
    response.cookies.set(LOCAL_SESSION_COOKIE, session.access_token, { ...localCookieOptions(), maxAge: session.expires_in });
    return response;
  } catch {
    return NextResponse.json({ error: "Sign-in service unavailable" }, { status: 503 });
  }
}
