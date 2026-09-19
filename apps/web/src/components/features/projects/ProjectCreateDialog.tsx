"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ProjectCreateDialogProps {
  onCreate: (name: string) => Promise<void>;
  isCreating?: boolean;
}

export function ProjectCreateDialog({ onCreate, isCreating }: ProjectCreateDialogProps) {
  const [show, setShow] = useState(false);
  const [name, setName] = useState("");

  const handleSubmit = async () => {
    if (!name.trim()) return;
    await onCreate(name.trim());
    setName("");
    setShow(false);
  };

  if (!show) {
    return (
      <Button variant="outline" size="sm" className="text-xs" onClick={() => setShow(true)}>
        <Plus size={12} className="mr-1" />
        New Project
      </Button>
    );
  }

  return (
    <div className="glow-card p-3 space-y-2">
      <h4 className="text-sm font-medium text-app-text">Create Project</h4>
      <input
        type="text"
        placeholder="Project name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
        className="w-full bg-app-surface border border-app-border rounded-md px-3 py-1.5 text-sm text-app-text"
        autoFocus
      />
      <div className="flex gap-2">
        <Button size="sm" className="text-xs glow-button" onClick={handleSubmit} disabled={!name.trim() || isCreating}>
          {isCreating ? "Creating..." : "Create"}
        </Button>
        <Button variant="ghost" size="sm" className="text-xs" onClick={() => setShow(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
