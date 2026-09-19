"use client";

import { Bot, Activity, CheckCircle, Clock } from "lucide-react";

interface AgentStatsProps {
  agentCount: number;
  taskCount: number;
  completedTasks: number;
  failedTasks: number;
  avgTime: string;
}

export function AgentStats({
  agentCount,
  taskCount,
  completedTasks,
  failedTasks,
  avgTime,
}: AgentStatsProps) {
  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      <div className="stat-glow p-4">
        <div className="flex items-center gap-2 mb-2">
          <Bot size={14} className="text-sky-400" />
          <span className="text-xs text-app-muted uppercase tracking-wider">
            Total Agents
          </span>
        </div>
        <p className="text-2xl font-bold text-app-text">{agentCount}</p>
      </div>
      <div className="stat-glow p-4">
        <div className="flex items-center gap-2 mb-2">
          <Activity size={14} className="text-purple-400" />
          <span className="text-xs text-app-muted uppercase tracking-wider">
            Total Tasks
          </span>
        </div>
        <p className="text-2xl font-bold text-app-text">{taskCount}</p>
      </div>
      <div className="stat-glow p-4">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle size={14} className="text-emerald-400" />
          <span className="text-xs text-app-muted uppercase tracking-wider">
            Completed
          </span>
        </div>
        <p className="text-2xl font-bold text-app-text">{completedTasks}</p>
        {failedTasks > 0 && (
          <p className="text-xs text-red-400 mt-1">
            {failedTasks} failed
          </p>
        )}
      </div>
      <div className="stat-glow p-4">
        <div className="flex items-center gap-2 mb-2">
          <Clock size={14} className="text-amber-400" />
          <span className="text-xs text-app-muted uppercase tracking-wider">
            Avg Time
          </span>
        </div>
        <p className="text-2xl font-bold text-app-text">{avgTime}s</p>
      </div>
    </div>
  );
}
