/**
 * AI agents: list, run tools, manage agent state.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, withProject } from "@/lib/api/client";
import type {
  SearchResults,
  EntityDetail,
  AgentTask,
  AgentTraceStep,
} from "@/lib/types";

export type { AgentTask } from "@/lib/types";

interface UseAgentsOptions {
  token: string | null;
  projectId: string | null;
}

export interface AgentRecord {
  id: string;
  name: string;
  type: string;
  config: Record<string, unknown>;
  status: string;
  created_at: string | null;
}

export interface AgentType { type: string; name: string; description: string }

export function useAgents({ token, projectId }: UseAgentsOptions) {
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [agentTypes, setAgentTypes] = useState<AgentType[]>([]);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResults | null>(null);
  const [entityDetail, setEntityDetail] = useState<EntityDetail | null>(null);
  const [searching, setSearching] = useState(false);

  const fetchAgents = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    try {
      const response = await apiFetch<AgentRecord[] | { agents: AgentRecord[] }>("/agents", { token, projectId });
      setAgents(Array.isArray(response) ? response : response.agents ?? []);
      const types = await apiFetch<{ types: AgentType[] }>("/agents/types", { token, projectId });
      setAgentTypes(types.types ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load agents");
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  const fetchTasks = useCallback(async (agentId: string) => {
    if (!token || !projectId) return;
    const response = await apiFetch<{ tasks: AgentTask[] }>(`/agents/${agentId}/tasks`, { token, projectId });
    setTasks(response.tasks ?? []);
  }, [token, projectId]);

  const fetchTaskDetail = useCallback(async (agentId: string, taskId: string) => {
    if (!token || !projectId) return null;
    const response = await apiFetch<{ task: AgentTask }>(`/agents/${agentId}/tasks/${taskId}`, { token, projectId });
    return response.task;
  }, [token, projectId]);

  const createAgent = useCallback(async (name: string, type: string) => {
    if (!token || !projectId) return false;
    await apiFetch("/agents", { method: "POST", token, projectId, body: { name, type } });
    await fetchAgents();
    return true;
  }, [token, projectId, fetchAgents]);

  const deleteAgent = useCallback(async (agentId: string) => {
    if (!token || !projectId) return;
    await apiFetch(`/agents/${agentId}`, { method: "DELETE", token, projectId });
    setAgents((prev) => prev.filter((agent) => agent.id !== agentId));
  }, [token, projectId]);

  const runAgent = useCallback(async (agentId: string, input: string, onTrace: (event: AgentTraceStep) => void, onDone: () => void) => {
    if (!token || !projectId) return;
    const response = await apiFetch<{ task_id: string }>(`/agents/${agentId}/run`, {
      method: "POST", token, projectId, body: { input: { query: input, source: "manual_trigger" } },
    });
    const stream = new EventSource(`${withProject(`/agents/${agentId}/tasks/${response.task_id}/stream?token=${encodeURIComponent(token)}`, projectId)}`);
    stream.onmessage = (event) => {
      try {
        const traceEvent = JSON.parse(event.data);
        onTrace(traceEvent);
        if (traceEvent.step === "complete" || traceEvent.status === "error") { stream.close(); onDone(); }
      } catch { /* ignore malformed trace events */ }
    };
    stream.onerror = () => { stream.close(); onDone(); };
  }, [token, projectId]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const runSearch = useCallback(
    async (query: string) => {
      if (!token || !projectId || !query.trim()) return;
      setSearching(true);
      setError(null);
      try {
        const results = await apiFetch<SearchResults>("/agents/search", {
          method: "POST",
          token,
          projectId,
          body: { query },
        });
        setSearchResults(results);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Search failed");
      } finally {
        setSearching(false);
      }
    },
    [token, projectId]
  );

  const fetchEntityDetail = useCallback(
    async (entityId: string) => {
      if (!token || !projectId) return;
      try {
        const detail = await apiFetch<{ entity: EntityDetail }>(`/kb/entities/${entityId}`, {
          token,
          projectId,
        });
        setEntityDetail(detail.entity);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load entity");
      }
    },
    [token, projectId]
  );

  return {
    agents,
    agentTypes,
    tasks,
    loading,
    error,
    searchResults,
    entityDetail,
    searching,
    runSearch,
    fetchEntityDetail,
    refresh: fetchAgents,
    fetchTasks,
    fetchTaskDetail,
    createAgent,
    deleteAgent,
    runAgent,
  };
}
