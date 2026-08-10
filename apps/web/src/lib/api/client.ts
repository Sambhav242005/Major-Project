/**
 * Central API client — single place for base URL + auth injection.
 *
 * Base URL comes from NEXT_PUBLIC_API_URL (env), falling back to localhost
 * for local dev. All backend calls should go through apiFetch() so tokens
 * are always attached and errors are normalized.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiError = {
  status: number;
  detail?: string;
};

export class ApiRequestError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, detail?: string) {
    super(detail || `Request failed with status ${status}`);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

type ApiFetchOptions = Omit<RequestInit, "body"> & {
  token?: string | null;
  body?: unknown;
};

/**
 * fetch wrapper that injects the bearer token and serializes JSON bodies.
 * Throws ApiRequestError on non-2xx with the backend's error detail.
 */
export async function apiFetch<T = unknown>(
  path: string,
  { token, body, headers, ...init }: ApiFetchOptions = {}
): Promise<T> {
  const finalHeaders: Record<string, string> = {
    ...(headers as Record<string, string> | undefined),
  };

  if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
  }
  if (token) {
    finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail: string | undefined;
    try {
      const data = await res.json();
      // Backend error shapes: {"detail": "..."} or {"error": {"message": "..."}}
      detail =
        data?.detail ??
        data?.error?.message ??
        (typeof data?.error === "string" ? data.error : undefined);
    } catch {
      // non-JSON error body — fall through
    }
    throw new ApiRequestError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
