import { LOCAL_SESSION_COOKIE, type LocalSession, type LocalUser } from "./local";

export { LOCAL_SESSION_COOKIE };

export class LocalAuthUnavailableError extends Error {
  constructor() {
    super("The sign-in service is temporarily unavailable. Please try again.");
    this.name = "LocalAuthUnavailableError";
  }
}

export function internalApiUrl(path: string): string {
  const base = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${path}`;
}

// The API verifies the signature, issuer, expiry and enabled user. A cookie's
// presence or decoded JWT payload never establishes authentication here.
export async function validatedLocalSession(token?: string): Promise<LocalSession | null> {
  if (!token) return null;
  try {
    const response = await fetch(internalApiUrl("/auth/me"), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
    if (response.status === 401 || response.status === 403) return null;
    if (!response.ok) throw new LocalAuthUnavailableError();
    const user = await response.json() as LocalUser;
    if (!user.id || !user.email) throw new LocalAuthUnavailableError();
    const encoded = token.split(".")[1];
    const payload = JSON.parse(atob(encoded.replace(/-/g, "+").replace(/_/g, "/")));
    const expiresAt = Number(payload.exp);
    const remaining = expiresAt - Math.floor(Date.now() / 1000);
    if (!Number.isFinite(expiresAt)) throw new LocalAuthUnavailableError();
    if (remaining <= 0) return null;
    return { access_token: token, user, expires_at: expiresAt, expires_in: remaining, token_type: "bearer" };
  } catch {
    throw new LocalAuthUnavailableError();
  }
}
