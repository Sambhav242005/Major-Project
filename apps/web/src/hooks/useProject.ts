/**
 * Project state — thin wrapper around the Zustand store.
 * Re-exports the store hook plus typed actions for convenience.
 */
"use client";

import { useProjectStore, Project } from "@/stores/project";

export type { Project };

export function useProject() {
  const projects = useProjectStore((s) => s.projects);
  const activeProjectId = useProjectStore((s) => s.activeProjectId);
  const loaded = useProjectStore((s) => s.loaded);
  const error = useProjectStore((s) => s.error);
  const offline = useProjectStore((s) => s.offline);
  const loadProjects = useProjectStore((s) => s.loadProjects);
  const setActiveProject = useProjectStore((s) => s.setActiveProject);
  const createProject = useProjectStore((s) => s.createProject);
  const renameProject = useProjectStore((s) => s.renameProject);

  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  return {
    projects,
    activeProjectId,
    activeProject,
    loaded,
    error,
    offline,
    loadProjects,
    setActiveProject,
    createProject,
    renameProject,
  };
}
