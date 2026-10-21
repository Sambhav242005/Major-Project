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
  const expected = process.env.NEXT_PUBLIC_APP_URL || request.url;
  try {
    return origin === new URL(expected).origin;
  } catch {
    return false;
  }
}
