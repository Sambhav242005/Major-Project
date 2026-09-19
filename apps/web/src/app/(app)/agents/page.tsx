"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch, withProject } from "@/lib/api/client";
import { useProjectStore } from "@/stores/project";
import { Plus } from "lucide-react";
import {
  AgentStats,
  AgentCard,
  AgentRunPanel,
  AgentLiveTrace,
  AgentTaskList,
  AgentCreateDialog,
  AgentTraceDialog,
} from "@/components/features/agents";

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
  input: string;
  output: any;
  error: string | null;
  trace: any[];
  started_at: string | null;
  completed_at: string | null;
}

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
  const [runError, setRunError] = useState<string>("");
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());
  const eventSourceRef = useRef<EventSource | null>(null);
  const { projects, activeProjectId, loadProjects } = useProjectStore();
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  const getToken = useCallback(async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || "mock-token";
  }, []);

  useEffect(() => {
    const init = async () => {
      const token = await getToken();
      if (!projects.length) await loadProjects(token);
    };
    init();
  }, []);

  const fetchAgents = useCallback(async () => {
    try {
      const token = await getToken();
      const [agentsData, typesData] = await Promise.all([
        apiFetch<{ agents: Agent[] }>("/agents", { token, projectId: activeProjectId }),
        apiFetch<{ types: AgentType[] }>("/agents/types", { token, projectId: activeProjectId }),
      ]);
      setAgents(agentsData.agents || []);
      setAgentTypes(typesData.types || []);
      setRunError("");
    } catch (e) {
      setRunError(e instanceof Error ? e.message : "Failed to fetch agents");
    } finally {
      setLoading(false);
    }
  }, [getToken, activeProjectId]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  const fetchTasks = useCallback(
    async (agentId: string) => {
      try {
        const token = await getToken();
        const data = await apiFetch<{ tasks: AgentTask[] }>(
          `/agents/${agentId}/tasks`,
          { token, projectId: activeProjectId }
        );
        setTasks(data.tasks || []);
      } catch (e) {
        console.error("Failed to fetch tasks:", e);
      }
    },
    [getToken, activeProjectId]
  );

  const fetchTaskDetail = useCallback(
    async (agentId: string, taskId: string) => {
      try {
        const token = await getToken();
        const data = await apiFetch<{ task: AgentTask }>(
          `/agents/${agentId}/tasks/${taskId}`,
          { token, projectId: activeProjectId }
        );
        return data.task;
      } catch (e) {
        console.error("Failed to fetch task detail:", e);
      }
      return null;
    },
    [getToken, activeProjectId]
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
        projectId: activeProjectId,
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
    setRunError("");
    setExpandedSteps(new Set());

    try {
      const token = await getToken();
      const data = await apiFetch<{ task_id: string }>(`/agents/${agentId}/run`, {
        method: "POST",
        token,
        projectId: activeProjectId,
        body: { input: { query: runInput.trim(), source: "manual_trigger" } },
      });
      const taskId = data.task_id;
      setRunInput("");

      const streamToken = await getToken();
      const evtSource = new EventSource(
        withProject(
          `/agents/${agentId}/tasks/${taskId}/stream?token=${streamToken}`,
          activeProjectId
        )
      );
      eventSourceRef.current = evtSource;

      evtSource.onmessage = (event) => {
        try {
          const traceEvent = JSON.parse(event.data);
          setLiveTrace((prev) => [...prev, traceEvent]);
          if (traceEvent.step === "complete" || traceEvent.status === "error") {
            evtSource.close();
            eventSourceRef.current = null;
            setRunning(null);
            fetchTasks(agentId);
          }
        } catch {}
      };

      evtSource.onerror = () => {
        evtSource.close();
        eventSourceRef.current = null;
        setRunning(null);
        fetchTasks(agentId);
      };
    } catch (e: any) {
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
        projectId: activeProjectId,
      });
      if (selectedAgent?.id === agentId) {
        setSelectedAgent(null);
        setTasks([]);
      }
      fetchAgents();
    } catch (e) {
      setRunError(e instanceof Error ? e.message : "Failed to delete agent");
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
                (new Date(t.completed_at).getTime() - new Date(t.started_at).getTime()) / 1000
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
            <a href="/dashboard" className="text-sm text-app-muted hover:text-app-text transition-colors">
              Dashboard
            </a>
            <span className="text-app-muted">/</span>
            <h1 className="font-display text-lg font-semibold text-app-text">Agents</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-app-muted">Project:</span>
            <span className="text-sm font-medium text-app-text">{activeProject?.name ?? "—"}</span>
            <a href="/projects" className="text-xs text-app-muted hover:text-app-text transition-colors">Manage</a>
            <a href="/chat" className="text-sm text-app-muted hover:text-app-text transition-colors">Chat</a>
            <a href="/graph" className="text-sm text-app-muted hover:text-app-text transition-colors">Graph</a>
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
        <AgentStats
          agentCount={agents.length}
          taskCount={tasks.length}
          completedTasks={completedTasks}
          failedTasks={failedTasks}
          avgTime={avgTime}
        />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: Agent Cards */}
          <div className="col-span-12 lg:col-span-4">
            <div className="mb-3">
              <h2 className="text-sm font-medium text-app-muted uppercase tracking-wider">Agents</h2>
            </div>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-5 h-5 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : agents.length === 0 ? (
              <div className="glow-card p-8 text-center">
                <p className="text-sm text-app-muted mb-1">No agents yet</p>
                <p className="text-xs text-app-muted">
                  {activeProject
                    ? `"${activeProject.name}" has no agents — create your first one`
                    : "Create your first agent to get started"}
                </p>
                <button
                  onClick={() => setShowCreate(true)}
                  className="text-xs px-3 py-1.5 rounded-lg bg-sky-500/10 text-app-text border border-sky-500/20 hover:bg-sky-500/20 transition-all mt-4"
                >
                  Create agent
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {agents.map((agent) => (
                  <AgentCard
                    key={agent.id}
                    agent={agent}
                    isSelected={selectedAgent?.id === agent.id}
                    isRunning={running === agent.id}
                    onSelect={selectAgent}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Center: Run Panel + Live Trace */}
          <div className="col-span-12 lg:col-span-5">
            {selectedAgent ? (
              <>
                <AgentRunPanel
                  agentName={selectedAgent.name}
                  runInput={runInput}
                  onInputChange={setRunInput}
                  onRun={() => handleRun(selectedAgent.id)}
                  isRunning={running === selectedAgent.id}
                  runError={runError}
                />
                <AgentLiveTrace
                  running={running === selectedAgent.id}
                  liveTrace={liveTrace}
                  expandedSteps={expandedSteps}
                  onToggleStep={(i) =>
                    setExpandedSteps((prev) => {
                      const next = new Set(prev);
                      if (next.has(i)) next.delete(i); else next.add(i);
                      return next;
                    })
                  }
                />
              </>
            ) : (
              <div className="glow-card p-12 text-center">
                <p className="text-sm text-app-muted mb-1">Select an agent to run</p>
                <p className="text-xs text-app-muted">Choose from the agents on the left or create a new one</p>
              </div>
            )}
          </div>

          {/* Right: Recent Tasks */}
          <div className="col-span-12 lg:col-span-3">
            <div className="mb-3">
              <h2 className="text-sm font-medium text-app-muted uppercase tracking-wider">Recent Tasks</h2>
            </div>
            {selectedAgent ? (
              <AgentTaskList
                tasks={tasks}
                onSelectTask={async (task) => {
                  setExpandedSteps(new Set());
                  setTraceLoading(true);
                  setShowTrace({ ...task, trace: [] });
                  const detail = await fetchTaskDetail(task.agent_id, task.id);
                  if (detail) setShowTrace(detail);
                  setTraceLoading(false);
                }}
              />
            ) : (
              <div className="glow-card p-6 text-center">
                <p className="text-xs text-app-muted">Select an agent to view tasks</p>
              </div>
            )}
          </div>
        </div>
      </main>

      <AgentCreateDialog
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        agentTypes={agentTypes}
        newName={newName}
        onNameChange={(v) => { setNewName(v); setCreateError(""); }}
        newType={newType}
        onTypeChange={setNewType}
        onCreate={handleCreate}
        creating={creating}
        createError={createError}
      />

      <AgentTraceDialog
        task={showTrace}
        loading={traceLoading}
        expandedSteps={expandedSteps}
        onToggleStep={(i) =>
          setExpandedSteps((prev) => {
            const next = new Set(prev);
            if (next.has(i)) next.delete(i); else next.add(i);
            return next;
          })
        }
        onExpandAll={() => {
          const trace = showTrace?.trace || [];
          setExpandedSteps((prev) =>
            prev.size === trace.length ? new Set() : new Set(trace.map((_: any, i: number) => i))
          );
        }}
        onClose={() => setShowTrace(null)}
      />
    </div>
  );
}
