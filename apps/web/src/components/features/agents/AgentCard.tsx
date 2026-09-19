"use client";

import { Bot, FileText, Brain, Search, CheckCircle, Zap, Trash2, Loader2 } from "lucide-react";

interface Agent {
  id: string;
  name: string;
  type: string;
  config: Record<string, any>;
  status: string;
  created_at: string | null;
}

const TYPE_ICONS: Record<string, any> = {
  summarizer: FileText,
  extractor: Brain,
  qa: Search,
  reviewer: CheckCircle,
  researcher: Zap,
};

const TYPE_COLORS: Record<string, string> = {
  summarizer: "tag-amber",
  extractor: "tag-purple",
  qa: "tag-cyan",
  reviewer: "tag-green",
  researcher: "tag-cyan",
};

interface AgentCardProps {
  agent: Agent;
  isSelected: boolean;
  isRunning: boolean;
  onSelect: (agent: Agent) => void;
  onDelete: (agentId: string) => void;
}

export function AgentCard({
  agent,
  isSelected,
  isRunning,
  onSelect,
  onDelete,
}: AgentCardProps) {
  const Icon = TYPE_ICONS[agent.type] || Bot;
  const colorTag = TYPE_COLORS[agent.type] || "tag-cyan";

  return (
    <div
      className={`glow-card p-4 cursor-pointer ${
        isSelected ? "glow-card-active" : ""
      }`}
      onClick={() => onSelect(agent)}
    >
      <div className="flex items-start gap-3">
        <div
          className={`w-9 h-9 rounded-lg flex items-center justify-center ${
            isSelected ? "bg-sky-500/20" : "bg-app-surface"
          }`}
        >
          <Icon
            size={16}
            className={isSelected ? "text-sky-400" : "text-app-muted"}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-app-text truncate">
              {agent.name}
            </h3>
            {isRunning && (
              <div className="pulse-dot text-sky-400 bg-sky-400" />
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${colorTag}`}>
              {agent.type}
            </span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded ${
                agent.status === "active" ? "tag-green" : "tag-red"
              }`}
            >
              {agent.status}
            </span>
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(agent.id);
          }}
          className="text-app-muted hover:text-red-400 transition-colors p-1"
          aria-label={`Delete ${agent.name}`}
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
