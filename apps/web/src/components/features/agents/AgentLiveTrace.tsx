"use client";

import type { AgentTraceStep } from "@/lib/types";

import {
  CheckCircle,
  AlertCircle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronRight,
  BarChart3,
} from "lucide-react";


interface AgentLiveTraceProps {
  running: boolean;
  liveTrace: AgentTraceStep[];
  expandedSteps: Set<number>;
  onToggleStep: (index: number) => void;
}

function PipelineNode({
  step,
  isLast,
}: {
  step: AgentTraceStep;
  isLast: boolean;
}) {
  return (
    <div className="flex items-center">
      <div
        className={`pipeline-node px-3 py-2 min-w-[80px] text-center ${
          step.status === "completed"
            ? "!border-emerald-500/40"
            : step.status === "error"
            ? "!border-red-500/40"
            : ""
        }`}
      >
        <p className="text-[10px] text-app-muted mb-0.5">{step.step}</p>
        <div className="flex items-center justify-center gap-1">
          {step.status === "completed" ? (
            <CheckCircle size={10} className="text-emerald-400" />
          ) : step.status === "error" ? (
            <AlertCircle size={10} className="text-red-400" />
          ) : (
            <Loader2 size={10} className="text-sky-400 animate-spin" />
          )}
          <span className="text-[10px] text-slate-400">
            {step.elapsed_seconds ? `${step.elapsed_seconds}s` : "..."}
          </span>
        </div>
      </div>
      {!isLast && <div className="pipeline-connector mx-1" />}
    </div>
  );
}

function StepDetail({
  step,
  expanded,
  onToggle,
}: {
  step: AgentTraceStep;
  expanded: boolean;
  onToggle: () => void;
}) {
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
    <div className={`trace-step ${expanded ? "trace-step-expanded" : ""}`}>
      <div className="flex items-center gap-3 p-3 cursor-pointer" onClick={onToggle}>
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
}

export function AgentLiveTrace({
  running,
  liveTrace,
  expandedSteps,
  onToggleStep,
}: AgentLiveTraceProps) {
  if (liveTrace.length === 0 && !running) {
    return (
      <div className="glow-card p-8 text-center">
        <BarChart3 size={28} className="text-app-muted mx-auto mb-3" />
        <p className="text-sm text-slate-400">Run the agent to see trace output</p>
      </div>
    );
  }

  return (
    <div className="glow-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 size={14} className="text-purple-400" />
        <h3 className="text-sm font-medium text-app-text">Live Trace</h3>
        {running && (
          <span className="text-[10px] px-1.5 py-0.5 rounded tag-purple">
            Running
          </span>
        )}
      </div>

      {/* Pipeline Overview */}
      <div className="flex items-center gap-1 mb-5 overflow-x-auto pb-2">
        {liveTrace.map((step, i) => (
          <PipelineNode
            key={i}
            step={step}
            isLast={i === liveTrace.length - 1}
          />
        ))}
      </div>

      {/* Detailed Steps */}
      <div className="space-y-2">
        {liveTrace.map((step, i) => (
          <StepDetail
            key={i}
            step={step}
            expanded={expandedSteps.has(i)}
            onToggle={() => onToggleStep(i)}
          />
        ))}
      </div>
    </div>
  );
}
