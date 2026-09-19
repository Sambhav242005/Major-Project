"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useAgents, AgentTask } from "@/hooks/useAgents";
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

export default function AgentsPage() {
  const { token } = useAuth();
  const { projects, activeProjectId } = useProjectStore();
  const { agents, agentTypes, tasks, loading, fetchTasks, fetchTaskDetail, createAgent, deleteAgent, runAgent } = useAgents({ token, projectId: activeProjectId });
  const [selectedAgent, setSelectedAgent] = useState<(typeof agents)[number] | null>(null);
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
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  const handleCreate = async () => {
    if (!newName.trim()) {
      setCreateError("Name is required");
      return;
    }
    setCreating(true);
    setCreateError("");
    try {
      await createAgent(newName.trim(), newType);
      setShowCreate(false);
      setNewName("");
      setNewType("summarizer");
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : "Failed to create agent");
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
      setRunInput("");
      await runAgent(agentId, runInput.trim(), (event) => setLiveTrace((prev) => [...prev, event]), () => {
        setRunning(null);
        fetchTasks(agentId);
      });
    } catch (e) {
      setRunError(e instanceof Error ? e.message : "Failed to start agent");
      setRunning(null);
    }
  };

  const handleDelete = async (agentId: string) => {
    try {
      await deleteAgent(agentId);
      if (selectedAgent?.id === agentId) {
        setSelectedAgent(null);
      }
    } catch (e) {
      setRunError(e instanceof Error ? e.message : "Failed to delete agent");
    }
  };

  const selectAgent = async (agent: (typeof agents)[number]) => {
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
