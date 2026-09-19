"use client";

import { Clock } from "lucide-react";
import { StatusPill } from "@/components/shared/StatusPill";

interface AgentTask {
  id: string;
  agent_id: string;
  status: string;
  input: string;
  output: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

interface AgentTaskListProps {
  tasks: AgentTask[];
  onSelectTask: (task: AgentTask) => void;
}

export function AgentTaskList({ tasks, onSelectTask }: AgentTaskListProps) {
  if (tasks.length === 0) {
    return (
      <div className="glow-card p-6 text-center">
        <Clock size={20} className="text-app-muted mx-auto mb-2" />
        <p className="text-xs text-app-muted">No tasks yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {tasks.slice(0, 10).map((task) => (
        <div
          key={task.id}
          className="glow-card p-3 cursor-pointer"
          onClick={() => onSelectTask(task)}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <StatusPill status={task.status} />
            <span className="text-[10px] text-app-muted font-mono">
              {task.id.slice(0, 8)}
            </span>
            <span
              className={`text-[10px] px-1 py-0.5 rounded ml-auto ${
                task.status === "completed"
                  ? "tag-green"
                  : task.status === "failed"
                  ? "tag-red"
                  : "tag-amber"
              }`}
            >
              {task.status}
            </span>
          </div>
          {task.started_at && (
            <p className="text-[10px] text-app-muted">
              {new Date(task.started_at).toLocaleString()}
            </p>
          )}
          {task.completed_at && task.started_at && (
            <p className="text-[10px] text-app-muted">
              {(
                (new Date(task.completed_at).getTime() -
                  new Date(task.started_at).getTime()) /
                1000
              ).toFixed(1)}
              s
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
