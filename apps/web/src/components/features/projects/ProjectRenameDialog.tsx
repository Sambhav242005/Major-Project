"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface ProjectRenameDialogProps {
  projectId: string;
  currentName: string;
  onRename: (id: string, name: string) => Promise<void>;
  onCancel: () => void;
  isRenaming?: boolean;
}

export function ProjectRenameDialog({ projectId, currentName, onRename, onCancel, isRenaming }: ProjectRenameDialogProps) {
  const [name, setName] = useState(currentName);

  const handleSubmit = async () => {
    if (!name.trim() || name.trim() === currentName) {
      onCancel();
      return;
    }
    await onRename(projectId, name.trim());
    onCancel();
  };

  return (
    <div className="glow-card p-3 space-y-2">
      <h4 className="text-sm font-medium text-app-text">Rename Project</h4>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
        className="w-full bg-app-surface border border-app-border rounded-md px-3 py-1.5 text-sm text-app-text"
        autoFocus
      />
      <div className="flex gap-2">
        <Button size="sm" className="text-xs" onClick={handleSubmit} disabled={isRenaming}>
          {isRenaming ? "Saving..." : "Save"}
        </Button>
        <Button variant="ghost" size="sm" className="text-xs" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
