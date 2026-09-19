"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { Check, ChevronDown, FolderKanban } from "lucide-react";
import { Select } from "@base-ui/react/select";
import { createClient } from "@/lib/supabase/client";
import { useProjectStore } from "@/stores/project";
import { cn } from "@/lib/utils";

/**
 * Header dropdown to switch the active project. Visible on every
 * authenticated page so it's always clear which project's data you're
 * viewing (chat, graph, documents, agents all scope to this).
 */
export function ProjectSwitcher() {
  const { projects, activeProjectId, loaded, error, offline, loadProjects, setActiveProject } =
    useProjectStore();
  const supabaseRef = useRef(createClient());

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabaseRef.current.auth.getSession();
      if (!session) return;
      await loadProjects(session.access_token);
    };
    init();
  }, [loadProjects]);

  const active = projects.find((p) => p.id === activeProjectId) ?? null;

  const label = active
    ? active.name
    : !loaded
      ? "Loading..."
      : offline
        ? "Backend offline"
        : error
          ? "Projects unavailable"
          : "No project";

  return (
    <Select.Root
      value={activeProjectId ?? ""}
      onValueChange={(value) => {
        if (value) setActiveProject(value);
      }}
    >
      <Select.Trigger
        className="group inline-flex h-8 items-center gap-1.5 rounded-lg border border-app-border-strong bg-app-surface-alt px-2.5 text-sm text-app-text hover:bg-app-card-hover transition-colors outline-none"
        aria-label="Switch project"
        title={error ?? undefined}
      >
        <FolderKanban className="size-4 text-app-muted" />
        <span className="max-w-32 truncate">{label}</span>
        <ChevronDown className="size-4 text-app-muted group-data-open:rotate-180 transition-transform" />
      </Select.Trigger>
      <Select.Portal>
        <Select.Positioner side="bottom" align="end" sideOffset={10} className="z-50">
          <Select.Popup className="min-w-56 rounded-lg border border-app-border-strong bg-app-card p-1 shadow-xl data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95">
            {projects.length > 0 ? (
              projects.map((p) => (
                <Select.Item
                  key={p.id}
                  value={p.id}
                  className="flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5 text-sm text-app-text data-selected:bg-brand-accent/15 data-highlighted:bg-app-surface-alt outline-none"
                >
                  <span className="truncate">{p.name}</span>
                  <Select.ItemIndicator className="ml-2 shrink-0">
                    <Check className="size-3.5 text-brand-accent" />
                  </Select.ItemIndicator>
                </Select.Item>
              ))
            ) : (
              <div className="px-2 py-1.5 text-sm text-app-muted">
                {offline
                  ? "Backend unreachable — check that the API server is running."
                  : error ?? "No projects"}
              </div>
            )}
            <Select.Separator className="my-1 h-px bg-app-border-strong" />
            <Link
              href="/projects"
              className={cn(
                "flex items-center justify-between rounded-md px-2 py-1.5 text-sm text-app-muted",
                "hover:bg-app-surface-alt hover:text-app-text transition-colors"
              )}
            >
              Manage projects
              <span aria-hidden>→</span>
            </Link>
          </Select.Popup>
        </Select.Positioner>
      </Select.Portal>
    </Select.Root>
  );
}
