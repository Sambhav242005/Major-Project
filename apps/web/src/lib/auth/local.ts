export const LOCAL_AUTH = process.env.NEXT_PUBLIC_AUTH_PROVIDER === "local";
export const LOCAL_SESSION_COOKIE = "akgb-session";

export type LocalUser = { id: string; email: string };
export type LocalSession = {
  access_token: string;
  user: LocalUser;
  expires_at: number;
  expires_in: number;
  token_type: "bearer";
};

export const localCookieOptions = () => ({
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
});

export function sameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  try {
    const configured = process.env.AUTH_ALLOWED_ORIGINS;
    // This private runtime setting is consumed only by server route handlers.
    // Never derive trusted origins from Host, forwarded headers or request.url.
    const allowed: unknown = configured === undefined
      ? [new URL(process.env.NEXT_PUBLIC_APP_URL || "").origin]
      : JSON.parse(configured);
    if (!Array.isArray(allowed) || allowed.length === 0 || !allowed.every((entry) => {
      if (typeof entry !== "string") return false;
      const url = new URL(entry);
      return ["https:", "http:"].includes(url.protocol) && url.origin === entry;
    })) return false;
    return origin !== null && allowed.includes(origin);
  } catch {
    return false;
  }
}
