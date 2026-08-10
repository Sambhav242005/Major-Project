"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, API_BASE } from "@/lib/api/client";
import Markdown from "react-markdown";
import {
  X,
  ChevronDown,
  ChevronRight,
  Play,
  Plus,
  Trash2,
  Bot,
  Brain,
  Search,
  FileText,
  CheckCircle,
  AlertCircle,
  Clock,
  Loader2,
  Zap,
  Activity,
  BarChart3,
  ArrowRight,
  ChevronsUpDown,
} from "lucide-react";

interface Agent {
  id: string;
  name: string;
  type: string;
  config: Record<string, any>;
  status: string;
  created_at: string | null;
}

interface AgentType {
  type: string;
  name: string;
  description: string;
}

interface AgentTask {
  id: string;
  agent_id: string;
  status: string;
  output: any;
  error: string | null;
  trace: any[];
  started_at: string | null;
  completed_at: string | null;
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

export default function AgentsPage() {
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentTypes, setAgentTypes] = useState<AgentType[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [showTrace, setShowTrace] = useState<AgentTask | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("summarizer");
  const [createError, setCreateError] = useState("");
  const [creating, setCreating] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [runInput, setRunInput] = useState("");
  const [liveTrace, setLiveTrace] = useState<any[]>([]);
  const [liveStatus, setLiveStatus] = useState<string>("");
  const [runError, setRunError] = useState<string>("");
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());
  const eventSourceRef = useRef<EventSource | null>(null);

  const getToken = useCallback(async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token || "mock-token";
  }, []);

  const fetchAgents = useCallback(async () => {
    try {
      const token = await getToken();
      const [agentsData, typesData] = await Promise.all([
        apiFetch<{ agents: Agent[] }>("/agents", { token }),
        apiFetch<{ types: AgentType[] }>("/agents/types", { token }),
      ]);
      setAgents(agentsData.agents || []);
      setAgentTypes(typesData.types || []);
    } catch (e) {
      console.error("Failed to fetch agents:", e);
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const fetchTasks = useCallback(
    async (agentId: string) => {
      try {
        const token = await getToken();
        const data = await apiFetch<{ tasks: AgentTask[] }>(
          `/agents/${agentId}/tasks`,
          { token }
        );
        setTasks(data.tasks || []);
      } catch (e) {
        console.error("Failed to fetch tasks:", e);
      }
    },
    [getToken]
  );

  const fetchTaskDetail = useCallback(
    async (agentId: string, taskId: string) => {
      try {
        const token = await getToken();
        const data = await apiFetch<{ task: AgentTask }>(
          `/agents/${agentId}/tasks/${taskId}`,
          { token }
        );
        return data.task;
      } catch (e) {
        console.error("Failed to fetch task detail:", e);
      }
      return null;
    },
    [getToken]
  );

  const handleCreate = async () => {
    if (!newName.trim()) {
      setCreateError("Name is required");
      return;
    }
    setCreating(true);
    setCreateError("");
    try {
      const token = await getToken();
      await apiFetch("/agents", {
        method: "POST",
        token,
        body: { name: newName.trim(), type: newType },
      });
      setShowCreate(false);
      setNewName("");
      setNewType("summarizer");
      fetchAgents();
    } catch (e: any) {
      setCreateError(e.detail || e.message || "Failed to create agent");
    } finally {
      setCreating(false);
    }
  };

  const handleRun = async (agentId: string) => {
    if (!runInput.trim()) return;
    setRunning(agentId);
    setLiveTrace([]);
    setLiveStatus("starting");
    setRunError("");
    setExpandedSteps(new Set());

    try {
      const token = await getToken();
      const data = await apiFetch<{ task_id: string }>(`/agents/${agentId}/run`, {
        method: "POST",
        token,
        body: {
          input: { query: runInput.trim(), source: "manual_trigger" },
        },
      });
      const taskId = data.task_id;
      setRunInput("");

      const streamToken = await getToken();
      const evtSource = new EventSource(
        `${API_BASE}/agents/${agentId}/tasks/${taskId}/stream?token=${streamToken}`
      );
      eventSourceRef.current = evtSource;

      evtSource.onmessage = (event) => {
        try {
          const traceEvent = JSON.parse(event.data);
          setLiveTrace((prev) => [...prev, traceEvent]);
          setLiveStatus(traceEvent.status || "running");
          if (
            traceEvent.step === "complete" ||
            traceEvent.status === "error"
          ) {
            evtSource.close();
            eventSourceRef.current = null;
            setRunning(null);
            fetchTasks(agentId);
          }
        } catch {
          // Skip malformed events
        }
      };

      evtSource.onerror = () => {
        evtSource.close();
        eventSourceRef.current = null;
        setRunning(null);
        fetchTasks(agentId);
      };
    } catch (e: any) {
      console.error("Failed to run agent:", e);
      setRunError(e.message || "Failed to start agent");
      setRunning(null);
    }
  };

  const handleDelete = async (agentId: string) => {
    try {
      const token = await getToken();
      await apiFetch(`/agents/${agentId}`, {
        method: "DELETE",
        token,
      });
      if (selectedAgent?.id === agentId) {
        setSelectedAgent(null);
        setTasks([]);
      }
      fetchAgents();
    } catch (e) {
      console.error("Failed to delete agent:", e);
    }
  };

  const selectAgent = async (agent: Agent) => {
    setSelectedAgent(agent);
    setRunInput("");
    await fetchTasks(agent.id);
  };

  const completedTasks = tasks.filter((t) => t.status === "completed").length;
  const failedTasks = tasks.filter((t) => t.status === "failed").length;
  const avgTime =
    tasks.length > 0
      ? (
          tasks.reduce((acc, t) => {
            if (t.started_at && t.completed_at) {
              return (
                acc +
                (new Date(t.completed_at).getTime() -
                  new Date(t.started_at).getTime()) /
                  1000
              );
            }
            return acc;
          }, 0) / tasks.length
        ).toFixed(1)
      : "0";

  return (
    <div className="agent-dark min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-app-border bg-app-bg/80 backdrop-blur-xl">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <a
              href="/dashboard"
              className="text-sm text-app-muted hover:text-app-text transition-colors"
            >
              Dashboard
            </a>
            <span className="text-app-muted">/</span>
            <h1 className="font-display text-lg font-semibold text-app-text">
              Agents
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <a
              href="/chat"
              className="text-sm text-app-muted hover:text-app-text transition-colors"
            >
              Chat
            </a>
            <a
              href="/graph"
              className="text-sm text-app-muted hover:text-app-text transition-colors"
            >
              Graph
            </a>
            <div className="w-px h-4 bg-app-border" />
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-sky-500/10 text-app-text border border-sky-500/20 text-sm font-medium hover:bg-sky-500/20 transition-all"
            >
              <Plus size={14} />
              New Agent
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-6">
        {/* KPI Stats Row */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="stat-glow p-4">
            <div className="flex items-center gap-2 mb-2">
              <Bot size={14} className="text-sky-400" />
              <span className="text-xs text-app-muted uppercase tracking-wider">
                Total Agents
              </span>
            </div>
            <p className="text-2xl font-bold text-app-text">{agents.length}</p>
          </div>
          <div className="stat-glow p-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity size={14} className="text-purple-400" />
              <span className="text-xs text-app-muted uppercase tracking-wider">
                Total Tasks
              </span>
            </div>
            <p className="text-2xl font-bold text-app-text">{tasks.length}</p>
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

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: Agent Cards */}
          <div className="col-span-12 lg:col-span-4">
            <div className="mb-3">
              <h2 className="text-sm font-medium text-app-muted uppercase tracking-wider">
                Agents
              </h2>
            </div>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 size={20} className="text-sky-400 animate-spin" />
              </div>
            ) : agents.length === 0 ? (
              <div className="glow-card p-8 text-center">
                <Bot
                  size={32}
                  className="text-app-muted mx-auto mb-3"
                />
                <p className="text-sm text-app-muted mb-1">No agents yet</p>
                <p className="text-xs text-app-muted">
                  Create your first agent to get started
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {agents.map((agent) => {
                  const Icon = TYPE_ICONS[agent.type] || Bot;
                  const colorTag = TYPE_COLORS[agent.type] || "tag-cyan";
                  const isSelected = selectedAgent?.id === agent.id;
                  const isRunning = running === agent.id;
                  return (
                    <div
                      key={agent.id}
                      className={`glow-card p-4 cursor-pointer ${
                        isSelected ? "glow-card-active" : ""
                      }`}
                      onClick={() => selectAgent(agent)}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                            isSelected
                              ? "bg-sky-500/20"
                              : "bg-app-surface"
                          }`}
                        >
                          <Icon
                            size={16}
                            className={
                              isSelected ? "text-sky-400" : "text-app-muted"
                            }
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
                            <span
                              className={`text-[10px] px-1.5 py-0.5 rounded ${colorTag}`}
                            >
                              {agent.type}
                            </span>
                            <span
                              className={`text-[10px] px-1.5 py-0.5 rounded ${
                                agent.status === "active"
                                  ? "tag-green"
                                  : "tag-red"
                              }`}
                            >
                              {agent.status}
                            </span>
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(agent.id);
                          }}
                          className="text-app-muted hover:text-red-400 transition-colors p-1"
                          aria-label={`Delete ${agent.name}`}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Center: Run Panel + Live Trace */}
          <div className="col-span-12 lg:col-span-5">
            {selectedAgent ? (
              <>
                {/* Run Panel */}
                <div className="glow-accent p-5 mb-6">
                  <div className="flex items-center gap-2 mb-3">
                    <Play size={14} className="text-purple-400" />
                    <h2 className="text-sm font-medium text-app-text">
                      Run {selectedAgent.name}
                    </h2>
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={runInput}
                      onChange={(e) => setRunInput(e.target.value)}
                      placeholder="Enter query or task..."
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && runInput.trim())
                          handleRun(selectedAgent.id);
                      }}
                      className="flex-1 h-9 px-3 rounded-lg bg-app-surface-alt border border-app-border-strong text-sm text-app-text placeholder:text-app-muted outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 transition-all"
                    />
                    <button
                      onClick={() => handleRun(selectedAgent.id)}
                      disabled={!runInput.trim() || running === selectedAgent.id}
                      className="flex items-center gap-2 px-4 h-9 rounded-lg bg-purple-500/20 text-app-text border border-purple-500/30 text-sm font-medium hover:bg-purple-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                    >
                      {running === selectedAgent.id ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Play size={14} />
                      )}
                      Run
                    </button>
                  </div>
                  {runError && (
                    <p className="text-xs text-red-400 mt-2 bg-red-500/10 px-3 py-2 rounded-lg border border-red-500/20">
                      {runError}
                    </p>
                  )}
                </div>

                {/* Live Trace Pipeline */}
                {running && liveTrace.length > 0 && (
                  <div className="glow-card p-5">
                    <div className="flex items-center gap-2 mb-4">
                      <div className="pulse-dot text-sky-400 bg-sky-400" />
                      <h3 className="text-sm font-medium text-app-text">
                        Live Trace
                      </h3>
                      <span className="text-[10px] px-1.5 py-0.5 rounded tag-cyan ml-auto">
                        {liveStatus}
                      </span>
                    </div>

                    {/* Pipeline Visualization */}
                    <div className="flex items-center gap-1 mb-4 overflow-x-auto pb-2">
                      {liveTrace.map((step, i) => (
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
                                <CheckCircle
                                  size={10}
                                  className="text-emerald-400"
                                />
                              ) : step.status === "error" ? (
                                <AlertCircle
                                  size={10}
                                  className="text-red-400"
                                />
                              ) : (
                                <Loader2
                                  size={10}
                                  className="text-sky-400 animate-spin"
                                />
                              )}
                              <span className="text-[10px] text-slate-400">
                                {step.elapsed_seconds
                                  ? `${step.elapsed_seconds}s`
                                  : "..."}
                              </span>
                            </div>
                          </div>
                          {i < liveTrace.length - 1 && (
                            <div className="pipeline-connector mx-1" />
                          )}
                        </div>
                      ))}
                    </div>

                    {/* Detailed Steps */}
                    <div className="space-y-2">
                      {liveTrace.map((step, i) => {
                        const expanded = expandedSteps.has(i);
                        const outputStr = step.output
                          ? typeof step.output === "string"
                            ? step.output
                            : JSON.stringify(step.output, null, 2)
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
                              onClick={() => {
                                setExpandedSteps((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(i)) next.delete(i);
                                  else next.add(i);
                                  return next;
                                });
                              }}
                            >
                              {step.status === "completed" ? (
                                <CheckCircle
                                  size={14}
                                  className="text-emerald-400 shrink-0"
                                />
                              ) : step.status === "error" ? (
                                <AlertCircle
                                  size={14}
                                  className="text-red-400 shrink-0"
                                />
                              ) : (
                                <Loader2
                                  size={14}
                                  className="text-sky-400 animate-spin shrink-0"
                                />
                              )}
                              <span className="text-xs font-medium text-app-text flex-1">
                                {step.step}
                              </span>
                              {step.elapsed_seconds && (
                                <span className="text-[10px] text-app-muted">
                                  {step.elapsed_seconds}s
                                </span>
                              )}
                              {outputStr &&
                                (expanded ? (
                                  <ChevronDown
                                    size={12}
                                    className="text-app-muted"
                                  />
                                ) : (
                                  <ChevronRight
                                    size={12}
                                    className="text-app-muted"
                                  />
                                ))}
                            </div>
                            {expanded && outputStr && (
                              <div className="px-3 pb-3">
                                <div className="output-box p-3 max-h-48 overflow-y-auto scrollbar-dark">
                                  {outputStr}
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

                {/* Empty state when no live trace */}
                {!running && liveTrace.length === 0 && (
                  <div className="glow-card p-8 text-center">
                    <BarChart3
                      size={28}
                      className="text-app-muted mx-auto mb-3"
                    />
                    <p className="text-sm text-slate-400">
                      Run the agent to see trace output
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="glow-card p-12 text-center">
                <Bot size={36} className="text-slate-700 mx-auto mb-4" />
                <p className="text-sm text-app-muted mb-1">
                  Select an agent to run
                </p>
                <p className="text-xs text-app-muted">
                  Choose from the agents on the left or create a new one
                </p>
              </div>
            )}
          </div>

          {/* Right: Recent Tasks */}
          <div className="col-span-12 lg:col-span-3">
            <div className="mb-3">
              <h2 className="text-sm font-medium text-app-muted uppercase tracking-wider">
                Recent Tasks
              </h2>
            </div>
            {selectedAgent ? (
              tasks.length === 0 ? (
                <div className="glow-card p-6 text-center">
                  <Clock size={20} className="text-app-muted mx-auto mb-2" />
                  <p className="text-xs text-app-muted">No tasks yet</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {tasks.slice(0, 10).map((task) => (
                    <div
                      key={task.id}
                      className="glow-card p-3 cursor-pointer"
                      onClick={async () => {
                        setExpandedSteps(new Set());
                        setTraceLoading(true);
                        setShowTrace(task);
                        const detail = await fetchTaskDetail(task.agent_id, task.id);
                        if (detail) setShowTrace(detail);
                        setTraceLoading(false);
                      }}
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            task.status === "completed"
                              ? "bg-emerald-400"
                              : task.status === "failed"
                              ? "bg-red-400"
                              : "bg-amber-400"
                          }`}
                        />
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
              )
            ) : (
              <div className="glow-card p-6 text-center">
                <p className="text-xs text-app-muted">
                  Select an agent to view tasks
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowCreate(false)}
          />
          <div className="relative glow-card p-6 w-full max-w-sm mx-4">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display text-base font-semibold text-app-text">
                New Agent
              </h2>
              <button
                onClick={() => setShowCreate(false)}
                className="text-app-muted hover:text-app-text transition-colors"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-app-muted mb-1.5 block">
                  Name
                </label>
                <input
                  value={newName}
                  onChange={(e) => {
                    setNewName(e.target.value);
                    setCreateError("");
                  }}
                  placeholder="e.g. Research Bot"
                  autoFocus
                  className="w-full h-9 px-3 rounded-lg bg-app-surface-alt border border-app-border-strong text-sm text-app-text placeholder:text-app-muted outline-none focus:border-sky-500/50 transition-all"
                />
              </div>
              <div>
                <label className="text-xs text-app-muted mb-1.5 block">
                  Type
                </label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
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
                onClick={handleCreate}
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
      )}

      {/* Trace Dialog */}
      {showTrace && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowTrace(null)}
          />
          <div className="relative glow-card p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto mx-4 scrollbar-dark">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display text-base font-semibold text-app-text">
                Task Trace
              </h2>
              <button
                onClick={() => setShowTrace(null)}
                className="text-app-muted hover:text-app-text transition-colors"
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            {traceLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={20} className="animate-spin text-app-muted" />
                <span className="ml-2 text-xs text-app-muted">Loading trace...</span>
              </div>
            )}

            <div className="flex items-center gap-2 mb-4">
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded ${
                  showTrace.status === "completed" ? "tag-green" : "tag-red"
                }`}
              >
                {showTrace.status}
              </span>
              <span className="text-[10px] text-app-muted font-mono">
                {showTrace.id}
              </span>
            </div>

            {showTrace.error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-4">
                <p className="text-xs text-red-400">{showTrace.error}</p>
              </div>
            )}

            {/* Pipeline */}
            {showTrace.trace && showTrace.trace.length > 0 && (
              <div className="flex items-center gap-1 mb-5 overflow-x-auto pb-2">
                {showTrace.trace.map((step: any, i: number) => (
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
                          <CheckCircle
                            size={10}
                            className="text-emerald-400"
                          />
                        ) : step.status === "error" ? (
                          <AlertCircle size={10} className="text-red-400" />
                        ) : (
                          <Clock size={10} className="text-app-muted" />
                        )}
                        <span className="text-[10px] text-slate-400">
                          {step.elapsed_seconds
                            ? `${step.elapsed_seconds}s`
                            : ""}
                        </span>
                      </div>
                    </div>
                    {i < showTrace.trace.length - 1 && (
                      <div className="pipeline-connector mx-1" />
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Detailed Steps */}
            <div className="mb-5">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-app-muted uppercase tracking-wider">
                  Steps
                </p>
                <button
                  onClick={() => {
                    const trace = showTrace.trace || [];
                    if (expandedSteps.size === trace.length) {
                      setExpandedSteps(new Set());
                    } else {
                      setExpandedSteps(new Set(trace.map((_: any, i: number) => i)));
                    }
                  }}
                  className="flex items-center gap-1 text-[10px] text-sky-400 hover:text-sky-300 transition-colors"
                >
                  <ChevronsUpDown size={10} />
                  {expandedSteps.size === (showTrace.trace || []).length
                    ? "Collapse All"
                    : "Expand All"}
                </button>
              </div>
              <div className="space-y-2">
                {(showTrace.trace || []).map((step: any, i: number) => {
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
                        step.arguments && `Arguments: ${JSON.stringify(step.arguments, null, 2)}`,
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
                        onClick={() => {
                          setExpandedSteps((prev) => {
                            const next = new Set(prev);
                            if (next.has(i)) next.delete(i);
                            else next.add(i);
                            return next;
                          });
                        }}
                      >
                        {step.status === "completed" ? (
                          <CheckCircle
                            size={14}
                            className="text-emerald-400 shrink-0"
                          />
                        ) : step.status === "error" ? (
                          <AlertCircle
                            size={14}
                            className="text-red-400 shrink-0"
                          />
                        ) : (
                          <Clock
                            size={14}
                            className="text-app-muted shrink-0"
                          />
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
                            <ChevronDown
                              size={12}
                              className="text-app-muted"
                            />
                          ) : (
                            <ChevronRight
                              size={12}
                              className="text-app-muted"
                            />
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

            {/* Final Output */}
            {showTrace.output && (
              <div>
                <p className="text-xs text-app-muted uppercase tracking-wider mb-2">
                  Final Output
                </p>
                <div className="output-box p-4 text-sm">
                  <Markdown>
                    {typeof showTrace.output === "string"
                      ? showTrace.output
                      : showTrace.output.response ||
                        JSON.stringify(showTrace.output, null, 2)}
                  </Markdown>
                </div>
                {showTrace.output.tool_calls &&
                  showTrace.output.tool_calls.length > 0 && (
                    <div className="mt-3">
                      <p className="text-[10px] text-app-muted uppercase tracking-wider mb-1.5">
                        Tool Calls
                      </p>
                      {showTrace.output.tool_calls.map(
                        (tc: any, i: number) => (
                          <div
                            key={i}
                            className="trace-step p-2 mb-1"
                          >
                            <span className="text-xs text-sky-400 font-medium">
                              {tc.tool}
                            </span>
                            {tc.result_preview && (
                              <p className="text-[10px] text-app-muted mt-1 truncate">
                                {tc.result_preview}
                              </p>
                            )}
                          </div>
                        )
                      )}
                    </div>
                  )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
