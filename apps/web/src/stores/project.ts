"use client";

import { create } from "zustand";
import { apiFetch, ApiRequestError } from "@/lib/api/client";

export interface Project {
  id: string;
  name: string;
  role: string;
  created_at?: string | null;
  member_count?: number;
  document_count?: number;
  entity_count?: number;
  chat_count?: number;
  agent_count?: number;
}

const STORAGE_KEY = "akgb.activeProject";

interface ProjectState {
  projects: Project[];
  activeProjectId: string | null;
  loaded: boolean;
  error: string | null;
  /** True when the last load failed because the backend is unreachable. */
  offline: boolean;
  loadProjects: (token: string) => Promise<void>;
  setActiveProject: (id: string) => void;
  createProject: (token: string, name: string) => Promise<Project | null>;
  renameProject: (token: string, id: string, name: string) => Promise<boolean>;
}

function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiRequestError) return e.message;
  if (e instanceof Error) return e.message;
  return fallback;
}

function readStoredId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  activeProjectId: readStoredId(),
  loaded: false,
  error: null,
  offline: false,

  loadProjects: async (token: string) => {
    try {
      const projects = await apiFetch<Project[]>("/projects", {
        token,
      });
      if (!Array.isArray(projects)) throw new Error("Invalid projects response");

      // Pick active: stored id still valid → keep; else first project.
      let active = projects.find((p) => p.id === get().activeProjectId)?.id ?? null;
      if (!active && projects.length > 0) {
        active = projects[0].id;
      }
      if (active) {
        try {
          localStorage.setItem(STORAGE_KEY, active);
        } catch {
          /* private mode */
        }
      }

      set({
        projects,
        activeProjectId: active,
        loaded: true,
        error: null,
        offline: false,
      });
    } catch (e) {
      const offline = e instanceof ApiRequestError && e.status === 0;
      set({
        error: errorMessage(e, "Failed to load projects"),
        loaded: true,
        offline,
      });
    }
  },

  setActiveProject: (id: string) => {
    set({ activeProjectId: id });
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* private mode */
    }
  },

  createProject: async (token: string, name: string) => {
    try {
      const created = await apiFetch<Project>("/projects", {
        method: "POST",
        token,
        body: { name },
      });
      set((state) => ({
        projects: [created, ...state.projects],
        activeProjectId: created.id,
        error: null,
        offline: false,
      }));
      try {
        localStorage.setItem(STORAGE_KEY, created.id);
      } catch {
        /* private mode */
      }
      return created;
    } catch (e) {
      set({ error: errorMessage(e, "Failed to create project") });
      return null;
    }
  },

  renameProject: async (token: string, id: string, name: string) => {
    try {
      const updated = await apiFetch<Project>(`/projects/${id}`, {
        method: "PATCH",
        token,
        body: { name },
      });
      set((state) => ({
        projects: state.projects.map((p) =>
          p.id === id ? { ...p, name: updated.name } : p
        ),
        error: null,
        offline: false,
      }));
      return true;
    } catch (e) {
      set({ error: errorMessage(e, "Failed to rename project") });
      return false;
    }
  },
}));
