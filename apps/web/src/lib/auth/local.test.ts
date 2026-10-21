import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});

const tokenFor = (expiresAt: number) => `header.${Buffer.from(JSON.stringify({ exp: expiresAt })).toString("base64url")}.signature`;

describe("local session verification", () => {
  it("never accepts a cookie without API verification", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("Unauthorized", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("API_INTERNAL_URL", "http://api:8000");
    const { validatedLocalSession } = await import("./local-server");
    expect(await validatedLocalSession(tokenFor(Math.floor(Date.now() / 1000) + 600))).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith("http://api:8000/auth/me", expect.objectContaining({ cache: "no-store" }));
  });

  it("returns a verified user and bearer token only for an unexpired session", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(Response.json({ id: "user-1", email: "member@example.com" }))));
    const { validatedLocalSession } = await import("./local-server");
    const token = tokenFor(Math.floor(Date.now() / 1000) + 600);
    expect(await validatedLocalSession(token)).toMatchObject({ access_token: token, user: { id: "user-1" }, token_type: "bearer" });
    expect(await validatedLocalSession(tokenFor(1))).toBeNull();
    await expect(validatedLocalSession("malformed")).rejects.toThrow("temporarily unavailable");
  });
});

describe("local login cookie boundary", () => {
  it("authenticates the gateway client IP with a server-only proxy secret", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_PROVIDER", "local");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://app.example.com");
    vi.stubEnv("AUTH_PROXY_SECRET", "private-server-proxy-secret");
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ session: { access_token: "token", expires_in: 600 } }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("@/app/auth/local-login/route");
    const response = await POST(new NextRequest("https://app.example.com/auth/local-login", {
      method: "POST",
      headers: { origin: "https://app.example.com", "X-AKGB-Client-IP": "192.168.1.10", "X-AKGB-Proxy-Secret": "browser-forgery" },
      body: JSON.stringify({ email: "member@example.com", password: "password" }),
    }));
    expect(fetchMock).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
      headers: expect.objectContaining({ "X-AKGB-Client-IP": "192.168.1.10", "X-AKGB-Proxy-Secret": "private-server-proxy-secret" }),
    }));
    expect(await response.text()).not.toContain("private-server-proxy-secret");
    expect(response.headers.get("set-cookie")).not.toContain("private-server-proxy-secret");
  });

  it("rejects cross-origin login before calling the backend", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_PROVIDER", "local");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://app.example.com");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("@/app/auth/local-login/route");
    const response = await POST(new NextRequest("https://app.example.com/auth/local-login", {
      method: "POST", headers: { origin: "https://attacker.example" },
      body: JSON.stringify({ email: "member@example.com", password: "password" }),
    }));
    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sets a secure HttpOnly cookie without exposing the token in the login response", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_PROVIDER", "local");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://app.example.com");
    vi.stubEnv("NODE_ENV", "production");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ session: { access_token: "real-api-token", expires_in: 600 } })));
    const { POST } = await import("@/app/auth/local-login/route");
    const response = await POST(new NextRequest("https://app.example.com/auth/local-login", {
      method: "POST", headers: { origin: "https://app.example.com" },
      body: JSON.stringify({ email: "member@example.com", password: "password" }),
    }));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ok: true });
    const cookie = response.headers.get("set-cookie");
    expect(cookie).toContain("akgb-session=real-api-token");
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("Secure");
    expect(cookie).toContain("SameSite=lax");
  });

  it("clears the session on same-origin logout and redirects form POST as GET", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_PROVIDER", "local");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://app.example.com");
    const { POST } = await import("@/app/auth/signout/route");
    const response = await POST(new NextRequest("https://app.example.com/auth/signout", { method: "POST", headers: { origin: "https://app.example.com" } }));
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("https://app.example.com/auth/signin");
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
  });

  it("does not accept a forged cookie on a protected page", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_PROVIDER", "local");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Unauthorized", { status: 401 })));
    const { middleware } = await import("@/middleware");
    const response = await middleware(new NextRequest("https://app.example.com/documents", {
      headers: { cookie: "akgb-session=forged-token" },
    }));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://app.example.com/auth/signin");
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
  });

  it("redirects logout to the public LAN origin behind the standalone container", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_PROVIDER", "local");
    vi.stubEnv("NEXT_PUBLIC_APP_URL", "https://192.168.1.100:13000");
    const { POST } = await import("@/app/auth/signout/route");
    const response = await POST(new NextRequest("https://0.0.0.0:3000/auth/signout", {
      method: "POST", headers: { origin: "https://192.168.1.100:13000" },
    }));
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("https://192.168.1.100:13000/auth/signin");
    expect(response.headers.get("set-cookie")).toContain("Max-Age=0");
  });

  it("leaves local login unavailable when Supabase is selected", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_PROVIDER", "supabase");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("@/app/auth/local-login/route");
    const response = await POST(new NextRequest("https://app.example.com/auth/local-login", { method: "POST" }));
    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each(["unavailable", "timeout"])("preserves the cookie when backend verification is %s", async (failure) => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_PROVIDER", "local");
    const fetchMock = vi.fn();
    if (failure === "timeout") fetchMock.mockRejectedValue(new DOMException("Timed out", "TimeoutError"));
    else fetchMock.mockImplementation(() => Promise.resolve(new Response("Unavailable", { status: 503 })));
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("@/app/auth/local-session/route");
    const { middleware } = await import("@/middleware");
    const headers = { cookie: `akgb-session=${tokenFor(Math.floor(Date.now() / 1000) + 600)}` };
    const sessionResponse = await GET(new NextRequest("https://app.example.com/auth/local-session", { headers }));
    const pageResponse = await middleware(new NextRequest("https://app.example.com/documents", { headers }));
    for (const response of [sessionResponse, pageResponse]) {
      expect(response.status).toBe(503);
      expect(response.headers.get("set-cookie")).toBeNull();
      expect(response.headers.get("location")).toBeNull();
      expect(response.headers.get("retry-after")).toBe("30");
    }
  });

  it("propagates a browser session outage without emitting a sign-out event", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Unavailable", { status: 503 })));
    const { createLocalClient } = await import("./local-client");
    const client = createLocalClient();
    const authListener = vi.fn();
    client.auth.onAuthStateChange(authListener);
    const result = await client.auth.getSession();
    expect(result.error?.message).toContain("temporarily unavailable");
    expect(authListener).not.toHaveBeenCalled();
  });
});
