/**
 * AI agents: list, run tools, manage agent state.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import { Agent } from "@/lib/validators";
import { SearchResults, EntityDetail } from "@/lib/types";

interface UseAgentsOptions {
  token: string | null;
  projectId: string | null;
}

export function useAgents({ token, projectId }: UseAgentsOptions) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResults | null>(null);
  const [entityDetail, setEntityDetail] = useState<EntityDetail | null>(null);
  const [searching, setSearching] = useState(false);

  const fetchAgents = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    try {
      const data = await apiFetch<Agent[]>("/agents", { token, projectId });
      setAgents(Array.isArray(data) ? data : []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load agents");
    } finally {
      setLoading(false);
    }
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
        const detail = await apiFetch<EntityDetail>(`/entities/${entityId}`, {
          token,
          projectId,
        });
        setEntityDetail(detail);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load entity");
      }
    },
    [token, projectId]
  );

  return {
    agents,
    loading,
    error,
    searchResults,
    entityDetail,
    searching,
    runSearch,
    fetchEntityDetail,
    refresh: fetchAgents,
  };
}
