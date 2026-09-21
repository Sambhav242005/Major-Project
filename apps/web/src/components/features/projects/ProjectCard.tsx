"use client";

import { Folder, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ProjectCardProps {
  project: { id: string; name: string; created_at?: string | null };
  isActive: boolean;
  onSelect: () => void;
  onRename: () => void;
  onDelete: () => void;
}

export function ProjectCard({ project, isActive, onSelect, onRename, onDelete }: ProjectCardProps) {
  return (
    <div
      className={`glow-card p-3 cursor-pointer ${isActive ? "glow-card-active" : ""}`}
      onClick={onSelect}
    >
      <div className="flex items-center gap-3">
        <Folder size={16} className={isActive ? "text-sky-400" : "text-app-muted"} />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-app-text truncate">{project.name}</p>
          <p className="text-[10px] text-app-muted">
            Created {project.created_at ? new Date(project.created_at).toLocaleDateString() : "—"}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={(e) => {
              e.stopPropagation();
              onRename();
            }}
          >
            <Pencil size={12} />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs hover:text-red-400"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
          >
            <Trash2 size={12} />
          </Button>
        </div>
      </div>
    </div>
  );
}
