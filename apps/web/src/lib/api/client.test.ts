import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("configured API destination", () => {
  it("uses the configured public backend for requests with project context", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.akgb.example");
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true })));
    vi.stubGlobal("fetch", fetchMock);
    const { API_BASE, apiFetch } = await import("./client");

    expect(API_BASE).toBe("https://api.akgb.example");
    await expect(apiFetch("/documents", { projectId: "team / 1", token: "token" })).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.akgb.example/documents?project_id=team%20%2F%201",
      expect.objectContaining({ headers: { Authorization: "Bearer token" } })
    );
  });

  it("preserves an existing query string when adding project context", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.akgb.example");
    const { withProject } = await import("./client");
    expect(withProject("/documents?limit=8", "project-1")).toBe(
      "https://api.akgb.example/documents?limit=8&project_id=project-1"
    );
    expect(withProject("/health")).toBe("https://api.akgb.example/health");
  });

  it("retains the local development default when the public URL is absent", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", undefined);
    const { withProject } = await import("./client");
    expect(withProject("/health")).toBe("http://localhost:8000/health");
  });
});
