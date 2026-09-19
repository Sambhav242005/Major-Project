"use client";

import {
  X,
  CheckCircle,
  AlertCircle,
  Clock,
  ChevronDown,
  ChevronRight,
  ChevronsUpDown,
  Loader2,
} from "lucide-react";
import Markdown from "react-markdown";

interface TraceStep {
  step: string;
  status: string;
  tool?: string;
  output?: any;
  error?: string;
  elapsed_seconds?: number;
  score?: number;
  result_preview?: string;
  arguments?: any;
  details?: any;
  refinement?: any;
}

interface AgentTask {
  id: string;
  agent_id: string;
  status: string;
  input: string;
  output: any;
  trace: TraceStep[] | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

interface AgentTraceDialogProps {
  task: AgentTask | null;
  loading: boolean;
  expandedSteps: Set<number>;
  onToggleStep: (index: number) => void;
  onExpandAll: () => void;
  onClose: () => void;
}

export function AgentTraceDialog({
  task,
  loading,
  expandedSteps,
  onToggleStep,
  onExpandAll,
  onClose,
}: AgentTraceDialogProps) {
  if (!task) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative glow-card p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto mx-4 scrollbar-dark">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-display text-base font-semibold text-app-text">
            Task Trace
          </h2>
          <button
            onClick={onClose}
            className="text-app-muted hover:text-app-text transition-colors"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin text-app-muted" />
            <span className="ml-2 text-xs text-app-muted">Loading trace...</span>
          </div>
        )}

        <div className="flex items-center gap-2 mb-4">
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded ${
              task.status === "completed" ? "tag-green" : "tag-red"
            }`}
          >
            {task.status}
          </span>
          <span className="text-[10px] text-app-muted font-mono">
            {task.id}
          </span>
        </div>

        {task.error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-4">
            <p className="text-xs text-red-400">{task.error}</p>
          </div>
        )}

        {/* Pipeline */}
        {task.trace && task.trace.length > 0 && (
          <div className="flex items-center gap-1 mb-5 overflow-x-auto pb-2">
            {task.trace.map((step, i) => (
              <div key={i} className="flex items-center">
                <div
                  className={`pipeline-node px-3 py-2 min-w-[80px] text-center ${
                    step.status === "completed"
                      ? "!border-emerald-500/40"
                      : step.status === "error"
                      ? "!border-red-500/40"
                      : ""
                  }`}
                >
                  <p className="text-[10px] text-app-muted mb-0.5">
                    {step.step}
                  </p>
                  <div className="flex items-center justify-center gap-1">
                    {step.status === "completed" ? (
                      <CheckCircle size={10} className="text-emerald-400" />
                    ) : step.status === "error" ? (
                      <AlertCircle size={10} className="text-red-400" />
                    ) : (
                      <Clock size={10} className="text-app-muted" />
                    )}
                    <span className="text-[10px] text-slate-400">
                      {step.elapsed_seconds ? `${step.elapsed_seconds}s` : ""}
                    </span>
                  </div>
                </div>
                {task.trace && i < task.trace.length - 1 && (
                  <div className="pipeline-connector mx-1" />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Detailed Steps */}
        {task.trace && task.trace.length > 0 && (
          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-app-muted uppercase tracking-wider">
                Steps
              </p>
              <button
                onClick={onExpandAll}
                className="flex items-center gap-1 text-[10px] text-sky-400 hover:text-sky-300 transition-colors"
              >
                <ChevronsUpDown size={10} />
                {expandedSteps.size === task.trace.length
                  ? "Collapse All"
                  : "Expand All"}
              </button>
            </div>
            <div className="space-y-2">
              {task.trace.map((step, i) => {
                const expanded = expandedSteps.has(i);
                const hasExpandableContent = !!(
                  step.output ||
                  step.result_preview ||
                  step.arguments ||
                  step.details ||
                  step.refinement
                );
                const detailContent = step.output
                  ? typeof step.output === "string"
                    ? step.output
                    : JSON.stringify(step.output, null, 2)
                  : step.step === "tool_execution"
                  ? [
                      step.tool && `Tool: ${step.tool}`,
                      step.arguments &&
                        `Arguments: ${JSON.stringify(step.arguments, null, 2)}`,
                      step.result_preview && `Result: ${step.result_preview}`,
                    ]
                      .filter(Boolean)
                      .join("\n\n")
                  : step.step === "evaluate"
                  ? `Score: ${step.score}\n\n${JSON.stringify(step.details, null, 2)}`
                  : step.step === "refine" && step.refinement
                  ? JSON.stringify(step.refinement, null, 2)
                  : null;

                return (
                  <div
                    key={i}
                    className={`trace-step ${
                      expanded ? "trace-step-expanded" : ""
                    }`}
                  >
                    <div
                      className="flex items-center gap-3 p-3 cursor-pointer"
                      onClick={() => onToggleStep(i)}
                    >
                      {step.status === "completed" ? (
                        <CheckCircle size={14} className="text-emerald-400 shrink-0" />
                      ) : step.status === "error" ? (
                        <AlertCircle size={14} className="text-red-400 shrink-0" />
                      ) : (
                        <Clock size={14} className="text-app-muted shrink-0" />
                      )}
                      {step.tool && (
                        <span className="text-[10px] text-sky-400 font-mono bg-sky-500/10 px-1.5 py-0.5 rounded">
                          {step.tool}
                        </span>
                      )}
                      <span className="text-xs font-medium text-app-text flex-1">
                        {step.step}
                      </span>
                      {step.elapsed_seconds && (
                        <span className="text-[10px] text-app-muted">
                          {step.elapsed_seconds}s
                        </span>
                      )}
                      {step.score !== undefined && (
                        <span className="text-[10px] text-emerald-400 font-mono">
                          {step.score}
                        </span>
                      )}
                      {hasExpandableContent &&
                        (expanded ? (
                          <ChevronDown size={12} className="text-app-muted" />
                        ) : (
                          <ChevronRight size={12} className="text-app-muted" />
                        ))}
                    </div>
                    {expanded && detailContent && (
                      <div className="px-3 pb-3">
                        <div className="output-box p-3 max-h-64 overflow-y-auto scrollbar-dark whitespace-pre-wrap text-[11px]">
                          {detailContent}
                        </div>
                      </div>
                    )}
                    {step.error && (
                      <div className="px-3 pb-3">
                        <p className="text-xs text-red-400 bg-red-500/10 px-2 py-1 rounded">
                          {step.error}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Final Output */}
        {task.output && (
          <div>
            <p className="text-xs text-app-muted uppercase tracking-wider mb-2">
              Final Output
            </p>
            <div className="output-box p-4 text-sm">
              <Markdown>
                {typeof task.output === "string"
                  ? task.output
                  : task.output.response ||
                    JSON.stringify(task.output, null, 2)}
              </Markdown>
            </div>
            {task.output.tool_calls && task.output.tool_calls.length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] text-app-muted uppercase tracking-wider mb-1.5">
                  Tool Calls
                </p>
                {task.output.tool_calls.map((tc: any, i: number) => (
                  <div key={i} className="trace-step p-2 mb-1">
                    <span className="text-xs text-sky-400 font-medium">
                      {tc.tool}
                    </span>
                    {tc.result_preview && (
                      <p className="text-[10px] text-app-muted mt-1 truncate">
                        {tc.result_preview}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
