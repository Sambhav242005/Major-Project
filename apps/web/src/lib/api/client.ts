/**
 * Central API client — single place for base URL + auth injection.
 *
 * Base URL comes from NEXT_PUBLIC_API_URL (env), falling back to localhost
 * for local dev. All backend calls should go through apiFetch() so tokens
 * are always attached and errors are normalized.
 */

// Read the env var WITHOUT a bare `process.env` access: Next inlines
// NEXT_PUBLIC_* at build time, but if that inlining doesn't happen (or the
// var is unset), a raw `process.env.X` throws ReferenceError in the browser
// (process is not defined) and silently turns API_BASE into a relative URL,
// which 404s against the Next origin. `typeof process` is safe everywhere.
function readEnv(name: string): string | undefined {
  if (typeof process === "undefined") return undefined;
  return (process.env as Record<string, string | undefined>)[name];
}

export const API_BASE = readEnv("NEXT_PUBLIC_API_URL") || "http://localhost:8000";

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
  projectId?: string | null;
  /** Milliseconds to wait before aborting. Default 15000. */
  timeoutMs?: number;
};

const DEFAULT_TIMEOUT_MS = 15000;

function humanError(status: number, detail?: string): string {
  if (detail) return detail;
  if (status === 401 || status === 403) return "You are not authorized to do that. Please sign in again.";
  if (status === 404) return "The requested resource was not found.";
  if (status >= 500) return "The server hit an error. Please try again in a moment.";
  return `Request failed with status ${status}`;
}

/**
 * Build an absolute backend URL: API_BASE + path, plus ?project_id= when a
 * project context is active. Handles paths that already carry a query string.
 */
export function withProject(path: string, projectId?: string | null): string {
  let url = `${API_BASE}${path}`;
  if (!projectId) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}project_id=${encodeURIComponent(projectId)}`;
}

/**
 * fetch wrapper that injects the bearer token and serializes JSON bodies.
 * Throws ApiRequestError on non-2xx or network failure (backend down,
 * timeout). Network failures get a friendly message instead of the raw
 * "Failed to fetch" TypeError.
 */
export async function apiFetch<T = unknown>(
  path: string,
  { token, body, headers, projectId, timeoutMs, ...init }: ApiFetchOptions = {}
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

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs ?? DEFAULT_TIMEOUT_MS);
  // If the caller supplied its own signal, chain it into ours.
  const onOuterAbort = () => controller.abort();
  init.signal?.addEventListener("abort", onOuterAbort);

  let res: Response;
  try {
    res = await fetch(withProject(path, projectId), {
      ...init,
      signal: controller.signal,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    const aborted = controller.signal.aborted;
    const message =
      (e as Error)?.name === "AbortError"
        ? aborted && !init.signal?.aborted
          ? `The server took too long to respond${path ? ` (${path})` : ""}. Please try again.`
          : "Request was cancelled."
        : "Cannot reach the server. Check that the backend is running and try again.";
    throw new ApiRequestError(0, message);
  } finally {
    clearTimeout(timeout);
    init.signal?.removeEventListener("abort", onOuterAbort);
  }

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
    throw new ApiRequestError(res.status, humanError(res.status, detail));
  }

  if (res.status === 204) {
    return undefined as T;
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiRequestError(0, "The server returned an unexpected response. Please try again.");
  }
}
