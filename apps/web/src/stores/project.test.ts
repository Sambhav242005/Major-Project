import { afterEach, describe, expect, it, vi } from "vitest";
import { useProjectStore } from "./project";

afterEach(() => { vi.unstubAllGlobals(); useProjectStore.getState().setIdentity(null); });

describe("project identity isolation", () => {
  it("retains a stored selection only for its recorded account", () => {
    const values = new Map([["akgb.activeProjectUser", "same-user"], ["akgb.activeProject", "remembered-project"]]);
    vi.stubGlobal("window", {});
    vi.stubGlobal("localStorage", { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) });
    useProjectStore.getState().setIdentity("same-user");
    expect(useProjectStore.getState().activeProjectId).toBe("remembered-project");
    useProjectStore.getState().setIdentity("different-user");
    expect(useProjectStore.getState().activeProjectId).toBeNull();
  });
  it("clears project metadata and active selection when accounts change", () => {
    useProjectStore.getState().setIdentity("user-one");
    useProjectStore.setState({ projects: [{ id: "private-project", name: "Private", role: "owner" }], activeProjectId: "private-project", loaded: true });
    useProjectStore.getState().setIdentity("user-two");
    expect(useProjectStore.getState()).toMatchObject({ identityId: "user-two", projects: [], activeProjectId: null, loaded: false });
  });
  it("ignores a previous account's in-flight project response", async () => {
    let finish: ((response: Response) => void) | undefined;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { finish = resolve; })));
    useProjectStore.getState().setIdentity("user-one");
    const pending = useProjectStore.getState().loadProjects("old-token");
    useProjectStore.getState().setIdentity("user-two");
    finish!(Response.json([{ id: "private-project", name: "Private", role: "owner" }]));
    await pending;
    expect(useProjectStore.getState()).toMatchObject({ projects: [], loaded: false, identityId: "user-two" });
  });
});
