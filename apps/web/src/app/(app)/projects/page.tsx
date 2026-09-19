"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { useProject } from "@/hooks/useProject";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { ProjectCard, ProjectCreateDialog, ProjectRenameDialog } from "@/components/features/projects";

export default function ProjectsPage() {
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const {
    projects,
    activeProjectId,
    loaded,
    error,
    loadProjects,
    setActiveProject,
    createProject,
    renameProject,
  } = useProject();

  const [createOpen, setCreateOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<{ id: string; name: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) await loadProjects(session.access_token);
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = async (name: string) => {
    setBusy(true);
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      const created = await createProject(session.access_token, name);
      if (created) {
        setCreateOpen(false);
        setFlash(`Created "${created.name}" and switched to it`);
      }
    }
    setBusy(false);
  };

  const handleRename = async (id: string, name: string) => {
    setBusy(true);
    const { data: { session } } = await supabase.auth.getSession();
    if (session && (await renameProject(session.access_token, id, name))) {
      setRenameTarget(null);
    }
    setBusy(false);
  };

  const handleSelect = (id: string) => {
    setActiveProject(id);
    const p = projects.find((proj) => proj.id === id);
    if (p) setFlash(`Switched to "${p.name}"`);
  };

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <DashboardHeader title="Projects" showBack backHref="/dashboard" />

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-display text-2xl font-semibold text-app-text mb-1">
              Manage Projects
            </h2>
            <p className="text-app-muted text-sm">
              Each project has its own documents, chat history, graph, and agents.
            </p>
          </div>
          <ProjectCreateDialog onCreate={handleCreate} isCreating={busy} />
        </div>

        {flash && (
          <div className="mb-6 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-600 dark:text-emerald-400">
            {flash}
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
            {error}
          </div>
        )}

        {!loaded ? (
          <div className="text-center py-16 text-app-muted">Loading projects...</div>
        ) : projects.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-app-text font-medium mb-1">No projects yet</p>
            <p className="text-app-muted text-sm mb-4">Create your first project to start building.</p>
            <ProjectCreateDialog onCreate={handleCreate} isCreating={busy} />
          </div>
        ) : (
          <div className="space-y-2">
            {projects.map((p) => (
              <ProjectCard
                key={p.id}
                project={p}
                isActive={p.id === activeProjectId}
                onSelect={() => handleSelect(p.id)}
                onRename={() => setRenameTarget({ id: p.id, name: p.name })}
                onDelete={() => {}}
              />
            ))}
          </div>
        )}
      </main>

      {renameTarget && (
        <ProjectRenameDialog
          projectId={renameTarget.id}
          currentName={renameTarget.name}
          onRename={handleRename}
          onCancel={() => setRenameTarget(null)}
          isRenaming={busy}
        />
      )}
    </div>
  );
}
