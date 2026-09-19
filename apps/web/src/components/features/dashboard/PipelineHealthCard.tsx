"use client";

import { Activity, AlertTriangle, CheckCircle } from "lucide-react";

interface PipelineHealthCardProps {
  health: {
    queue_depth: number;
    failed_count: number;
    success_rate: number;
  };
}

export function PipelineHealthCard({ health }: PipelineHealthCardProps) {
  const isHealthy = health.failed_count === 0 && health.queue_depth < 10;

  return (
    <div className="glow-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Activity size={16} className={isHealthy ? "text-emerald-400" : "text-amber-400"} />
        <h3 className="text-sm font-medium text-app-text">Pipeline Health</h3>
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs text-app-muted">Success Rate</span>
          <span className="text-sm font-medium text-app-text">{health.success_rate}%</span>
        </div>
        <div className="w-full bg-app-surface rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full ${health.success_rate > 90 ? "bg-emerald-400" : "bg-amber-400"}`}
            style={{ width: `${health.success_rate}%` }}
          />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-app-muted">Queue Depth</span>
          <span className="text-sm text-app-text">{health.queue_depth}</span>
        </div>
        {health.failed_count > 0 && (
          <div className="flex items-center gap-1 text-xs text-red-400">
            <AlertTriangle size={12} />
            {health.failed_count} failed
          </div>
        )}
        {isHealthy && (
          <div className="flex items-center gap-1 text-xs text-emerald-400">
            <CheckCircle size={12} />
            All systems operational
          </div>
        )}
      </div>
    </div>
  );
}
