"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { useProjectStore, type Project } from "@/stores/project";
import { DashboardHeader } from "@/components/dashboard-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Check, Pencil, Plus } from "lucide-react";

export default function ProjectsPage() {
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const { projects, activeProjectId, loaded, error, loadProjects, setActiveProject, createProject, renameProject } =
    useProjectStore();

  const [createOpen, setCreateOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renaming, setRenaming] = useState<Project | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  const load = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) await loadProjects(session.access_token);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      const created = await createProject(session.access_token, trimmed);
      if (created) {
        setCreateOpen(false);
        setName("");
        setFlash(`Created "${created.name}" and switched to it`);
      }
    }
    setBusy(false);
  };

  const handleRename = async () => {
    if (!renaming) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    const { data: { session } } = await supabase.auth.getSession();
    if (session && (await renameProject(session.access_token, renaming.id, trimmed))) {
      setRenameOpen(false);
      setRenaming(null);
      setName("");
    }
    setBusy(false);
  };

  const switchTo = async (p: Project) => {
    setActiveProject(p.id);
    setFlash(`Switched to "${p.name}"`);
  };

  const openRename = (p: Project) => {
    setRenaming(p);
    setName(p.name);
    setRenameOpen(true);
  };

  const canRename = (p: Project) => p.role === "owner" || p.role === "editor";

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
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" />
            New Project
          </Button>
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
          <Card className="bg-app-card border border-app-border">
            <CardContent className="py-16 text-center">
              <p className="text-app-text font-medium mb-1">No projects yet</p>
              <p className="text-app-muted text-sm mb-4">
                Create your first project to start building.
              </p>
              <Button onClick={() => setCreateOpen(true)}>
                <Plus className="size-4" />
                New Project
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card className="bg-app-card border border-app-border">
            <CardContent className="p-0">
              <ul className="divide-y divide-app-border">
                {projects.map((p) => {
                  const active = p.id === activeProjectId;
                  return (
                    <li
                      key={p.id}
                      className="flex items-center gap-4 px-5 py-4"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-app-text truncate">
                            {p.name}
                          </span>
                          {active && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-brand-accent/15 px-2 py-0.5 text-[11px] font-medium text-app-text">
                              <Check className="size-3 text-brand-accent" />
                              Active
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-app-muted mt-0.5">
                          {p.member_count ?? 0} member{(p.member_count ?? 0) === 1 ? "" : "s"} ·{" "}
                          {p.document_count ?? 0} docs · {p.entity_count ?? 0} entities ·{" "}
                          {p.chat_count ?? 0} chats · {p.agent_count ?? 0} agents
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {canRename(p) && (
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => openRename(p)}
                            aria-label={`Rename ${p.name}`}
                          >
                            <Pencil className="size-3.5" />
                          </Button>
                        )}
                        {!active ? (
                          <Button variant="outline" size="sm" onClick={() => switchTo(p)}>
                            Switch
                          </Button>
                        ) : (
                          <span className="text-xs text-app-muted px-2">
                            {p.role}
                          </span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </CardContent>
          </Card>
        )}
      </main>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Project</DialogTitle>
            <DialogDescription>
              A project keeps documents, chats, graph, and agents together.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && !busy && handleCreate()}
          />
          <DialogFooter>
            <Button onClick={() => setCreateOpen(false)} variant="outline">
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={busy || !name.trim()}>
              {busy ? "Creating..." : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename dialog */}
      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename Project</DialogTitle>
            <DialogDescription>
              {renaming ? `Rename "${renaming.name}"` : "Rename this project"}
            </DialogDescription>
          </DialogHeader>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && !busy && handleRename()}
          />
          <DialogFooter>
            <Button onClick={() => setRenameOpen(false)} variant="outline">
              Cancel
            </Button>
            <Button onClick={handleRename} disabled={busy || !name.trim()}>
              {busy ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
