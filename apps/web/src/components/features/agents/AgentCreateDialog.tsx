"use client";

import { X, Plus, Loader2 } from "lucide-react";

interface AgentType {
  type: string;
  name: string;
  description: string;
}

interface AgentCreateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  agentTypes: AgentType[];
  newName: string;
  onNameChange: (name: string) => void;
  newType: string;
  onTypeChange: (type: string) => void;
  onCreate: () => void;
  creating: boolean;
  createError: string | null;
}

export function AgentCreateDialog({
  isOpen,
  onClose,
  agentTypes,
  newName,
  onNameChange,
  newType,
  onTypeChange,
  onCreate,
  creating,
  createError,
}: AgentCreateDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative glow-card p-6 w-full max-w-sm mx-4">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-display text-base font-semibold text-app-text">
            New Agent
          </h2>
          <button
            onClick={onClose}
            className="text-app-muted hover:text-app-text transition-colors"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-xs text-app-muted mb-1.5 block">Name</label>
            <input
              value={newName}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="e.g. Research Bot"
              autoFocus
              className="w-full h-9 px-3 rounded-lg bg-app-surface-alt border border-app-border-strong text-sm text-app-text placeholder:text-app-muted outline-none focus:border-sky-500/50 transition-all"
            />
          </div>
          <div>
            <label className="text-xs text-app-muted mb-1.5 block">Type</label>
            <select
              value={newType}
              onChange={(e) => onTypeChange(e.target.value)}
              className="w-full h-9 px-3 rounded-lg bg-app-surface-alt border border-app-border-strong text-sm text-app-text outline-none focus:border-sky-500/50 transition-all"
            >
              {agentTypes.map((t) => (
                <option key={t.type} value={t.type} className="bg-app-card">
                  {t.name}
                </option>
              ))}
            </select>
            <p className="text-[10px] text-app-muted mt-1">
              {agentTypes.find((t) => t.type === newType)?.description}
            </p>
          </div>
          {createError && (
            <p className="text-xs text-red-400 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">
              {createError}
            </p>
          )}
          <button
            onClick={onCreate}
            disabled={!newName.trim() || creating}
            className="w-full h-9 rounded-lg bg-sky-500/20 text-app-text border border-sky-500/30 text-sm font-medium hover:bg-sky-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
          >
            {creating ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Plus size={14} />
            )}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}
