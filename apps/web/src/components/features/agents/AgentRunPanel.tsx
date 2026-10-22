"use client";

import { Play, Loader2 } from "lucide-react";

interface AgentRunPanelProps {
  agentName: string;
  runInput: string;
  onInputChange: (value: string) => void;
  onRun: () => void;
  isRunning: boolean;
  runError: string | null;
  unavailableReason?: string;
}

export function AgentRunPanel({
  agentName,
  runInput,
  onInputChange,
  onRun,
  isRunning,
  runError,
  unavailableReason,
}: AgentRunPanelProps) {
  return (
    <div className="glow-accent p-5 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <Play size={14} className="text-purple-400" />
        <h2 className="text-sm font-medium text-app-text">
          Run {agentName}
        </h2>
      </div>
      <div className="flex gap-2">
        <input
          value={runInput}
          disabled={!!unavailableReason}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder="Enter query or task..."
          onKeyDown={(e) => {
            if (e.key === "Enter" && runInput.trim()) onRun();
          }}
          className="flex-1 h-9 px-3 rounded-lg bg-app-surface-alt border border-app-border-strong text-sm text-app-text placeholder:text-app-muted outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 transition-all"
        />
        <button
          onClick={onRun}
          disabled={!runInput.trim() || isRunning || !!unavailableReason}
          className="flex items-center gap-2 px-4 h-9 rounded-lg bg-purple-500/20 text-app-text border border-purple-500/30 text-sm font-medium hover:bg-purple-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          {isRunning ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Play size={14} />
          )}
          Run
        </button>
      </div>
      {unavailableReason && <p className="text-xs text-amber-400 mt-2">{unavailableReason}</p>}
      {runError && (
        <p className="text-xs text-red-400 mt-2 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">
          {runError}
        </p>
      )}
    </div>
  );
}
