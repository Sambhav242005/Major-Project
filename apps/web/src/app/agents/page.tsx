"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

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

const TYPE_COLORS: Record<string, string> = {
  summarizer: "bg-amber/10 text-amber",
  extractor: "bg-verified/10 text-verified",
  qa: "bg-slate/10 text-slate",
  reviewer: "bg-rust/10 text-rust",
};

export default function AgentsPage() {
  const supabase = createClient();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentTypes, setAgentTypes] = useState<AgentType[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [showTrace, setShowTrace] = useState<AgentTask | null>(null);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("summarizer");
  const [running, setRunning] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const headers = { Authorization: `Bearer ${session.access_token}` };

      const [agentsRes, typesRes] = await Promise.all([
        fetch("http://localhost:8000/agents", { headers }),
        fetch("http://localhost:8000/agents/types", { headers }),
      ]);

      if (agentsRes.ok) {
        const data = await agentsRes.json();
        setAgents(data.agents || []);
      }
      if (typesRes.ok) {
        const data = await typesRes.json();
        setAgentTypes(data.types || []);
      }
    } catch (e) {
      console.error("Failed to fetch agents:", e);
    } finally {
      setLoading(false);
    }
  }, [supabase]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const fetchTasks = useCallback(
    async (agentId: string) => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const res = await fetch(`http://localhost:8000/agents/${agentId}/tasks`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });

        if (res.ok) {
          const data = await res.json();
          setTasks(data.tasks || []);
        }
      } catch (e) {
        console.error("Failed to fetch tasks:", e);
      }
    },
    [supabase]
  );

  const handleCreate = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch("http://localhost:8000/agents", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: newName, type: newType }),
      });

      if (res.ok) {
        setShowCreate(false);
        setNewName("");
        setNewType("summarizer");
        fetchAgents();
      }
    } catch (e) {
      console.error("Failed to create agent:", e);
    }
  };

  const handleRun = async (agentId: string) => {
    setRunning(agentId);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch(`http://localhost:8000/agents/${agentId}/run`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ input: { source: "manual_trigger" } }),
      });

      if (res.ok) {
        const data = await res.json();
        // Refresh tasks for this agent
        fetchTasks(agentId);
        // If task completed, show trace
        if (data.task_id) {
          setTimeout(async () => {
            const taskRes = await fetch(
              `http://localhost:8000/agents/${agentId}/tasks/${data.task_id}`,
              { headers: { Authorization: `Bearer ${session.access_token}` } }
            );
            if (taskRes.ok) {
              const taskData = await taskRes.json();
              setShowTrace(taskData.task);
            }
          }, 2000);
        }
      }
    } catch (e) {
      console.error("Failed to run agent:", e);
    } finally {
      setRunning(null);
    }
  };

  const handleDelete = async (agentId: string) => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      await fetch(`http://localhost:8000/agents/${agentId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });

      fetchAgents();
    } catch (e) {
      console.error("Failed to delete agent:", e);
    }
  };

  const selectAgent = async (agent: Agent) => {
    setSelectedAgent(agent);
    await fetchTasks(agent.id);
  };

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-slate/20 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-slate hover:text-ink transition-colors">
              ← Dashboard
            </Link>
            <h1 className="font-display text-xl font-semibold text-ink">
              Agent Management
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/documents" className="text-sm text-slate hover:text-ink transition-colors">
              Documents
            </Link>
            <Link href="/chat" className="text-sm text-slate hover:text-ink transition-colors">
              Chat
            </Link>
            <Link href="/graph" className="text-sm text-slate hover:text-ink transition-colors">
              Graph
            </Link>
            <Link href="/mcp" className="text-sm text-slate hover:text-ink transition-colors">
              MCP
            </Link>
            <form action="/auth/signout" method="post">
              <button type="submit" className="text-sm text-rust hover:underline">
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <p className="text-slate">
            Create and manage AI agents for knowledge extraction and analysis
          </p>
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger render={<Button />}>Create Agent</DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle className="font-display">Create New Agent</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div>
                  <label className="text-sm font-medium text-ink mb-1 block">Name</label>
                  <Input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="My Agent"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-ink mb-1 block">Type</label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    className="w-full rounded-md border border-slate/20 bg-white px-3 py-2 text-sm text-ink"
                  >
                    {agentTypes.map((t) => (
                      <option key={t.type} value={t.type}>
                        {t.name} — {t.description}
                      </option>
                    ))}
                  </select>
                </div>
                <Button onClick={handleCreate} disabled={!newName.trim()} className="w-full">
                  Create
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {loading ? (
          <div className="text-center py-12 text-slate">Loading agents...</div>
        ) : agents.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-ink font-medium mb-1">No agents yet</p>
              <p className="text-slate text-sm">
                Create your first agent to start automating knowledge extraction
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <Card
                key={agent.id}
                className={`cursor-pointer transition-colors ${
                  selectedAgent?.id === agent.id
                    ? "border-amber/50 ring-1 ring-amber/20"
                    : "hover:border-slate/40"
                }`}
                onClick={() => selectAgent(agent)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="font-display text-base">
                        {agent.name}
                      </CardTitle>
                      <Badge className={`mt-1 ${TYPE_COLORS[agent.type] || "bg-slate/10 text-slate"}`}>
                        {agent.type}
                      </Badge>
                    </div>
                    <Badge variant={agent.status === "active" ? "default" : "secondary"}>
                      {agent.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-slate mb-3">
                    {agentTypes.find((t) => t.type === agent.type)?.description || agent.type}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRun(agent.id);
                      }}
                      disabled={running === agent.id}
                    >
                      {running === agent.id ? "Running..." : "Run Now"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(agent.id);
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Selected Agent Tasks */}
        {selectedAgent && (
          <Card className="mt-8">
            <CardHeader>
              <CardTitle className="font-display text-lg">
                Recent Tasks — {selectedAgent.name}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {tasks.length === 0 ? (
                <p className="text-sm text-slate">No tasks yet. Run the agent to see results.</p>
              ) : (
                <div className="space-y-3">
                  {tasks.map((task) => (
                    <div
                      key={task.id}
                      className="flex items-center gap-4 p-3 bg-paper rounded-lg border border-slate/10 cursor-pointer hover:border-slate/30 transition-colors"
                      onClick={() => setShowTrace(task)}
                    >
                      <Badge variant={task.status === "completed" ? "default" : task.status === "failed" ? "destructive" : "secondary"}>
                        {task.status}
                      </Badge>
                      <span className="text-sm text-ink font-mono">
                        {task.id.slice(0, 8)}...
                      </span>
                      {task.started_at && (
                        <span className="text-xs text-slate ml-auto">
                          {new Date(task.started_at).toLocaleString()}
                        </span>
                      )}
                      {task.completed_at && task.started_at && (
                        <span className="text-xs text-slate">
                          {((new Date(task.completed_at).getTime() - new Date(task.started_at).getTime()) / 1000).toFixed(1)}s
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Trace Dialog */}
        <Dialog open={!!showTrace} onOpenChange={() => setShowTrace(null)}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-display">Task Trace</DialogTitle>
            </DialogHeader>
            {showTrace && (
              <div className="space-y-3 mt-4">
                <div className="flex items-center gap-2">
                  <Badge variant={showTrace.status === "completed" ? "default" : "destructive"}>
                    {showTrace.status}
                  </Badge>
                  <span className="text-sm font-mono text-slate">{showTrace.id}</span>
                </div>

                {showTrace.error && (
                  <div className="bg-rust/10 border border-rust/20 rounded-lg p-3">
                    <p className="text-sm text-rust font-medium">Error</p>
                    <p className="text-sm text-rust">{showTrace.error}</p>
                  </div>
                )}

                <div>
                  <p className="text-sm font-medium text-ink mb-2">Trace Steps</p>
                  <div className="space-y-2">
                    {(showTrace.trace || []).map((step: any, i: number) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 p-2 bg-paper rounded border border-slate/10"
                      >
                        <Badge
                          variant={
                            step.status === "completed"
                              ? "default"
                              : step.status === "error"
                              ? "destructive"
                              : "secondary"
                          }
                          className="mt-0.5"
                        >
                          {step.status}
                        </Badge>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-ink">{step.step}</p>
                          {step.output && (
                            <p className="text-xs text-slate mt-1 truncate">
                              {typeof step.output === "string"
                                ? step.output.slice(0, 200)
                                : JSON.stringify(step.output).slice(0, 200)}
                            </p>
                          )}
                          {step.error && (
                            <p className="text-xs text-rust mt-1">{step.error}</p>
                          )}
                          {step.elapsed_seconds && (
                            <p className="text-xs text-slate mt-1">
                              {step.elapsed_seconds}s
                            </p>
                          )}
                        </div>
                        {step.timestamp && (
                          <span className="text-xs text-slate whitespace-nowrap">
                            {new Date(step.timestamp).toLocaleTimeString()}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {showTrace.output && (
                  <div>
                    <p className="text-sm font-medium text-ink mb-1">Final Output</p>
                    <pre className="bg-paper rounded-lg p-3 text-xs text-ink overflow-x-auto border border-slate/10">
                      {JSON.stringify(showTrace.output, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}
