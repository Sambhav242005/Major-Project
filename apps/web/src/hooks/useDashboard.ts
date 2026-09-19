/**
 * Dashboard summary: fetch stats with optional polling.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api/client";
export interface DashboardData {
  total_documents: number;
  total_relationships: number;
  total_chats: number;
  active_agents: number;
  document_count: number;
  total_chunks: number;
  total_entities: number;
  recent_activity: Array<{
    id: string;
    action: string;
    resource_type: string;
    resource_id: string | null;
    created_at: string | null;
  }>;
  failed_documents: Array<{
    id: string;
    filename: string;
    error_message: string | null;
    uploaded_at: string | null;
  }>;
  pipeline_health: {
    queue_depth: number;
    failed_count: number;
    success_rate: number;
  };
}

interface UseDashboardOptions {
  token: string | null;
  projectId: string | null;
  /** Poll interval in ms. 0 = no polling. Default 30000. */
  pollInterval?: number;
}

export function useDashboard({
  token,
  projectId,
  pollInterval = 30000,
}: UseDashboardOptions) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchSummary = useCallback(async () => {
    if (!token || !projectId) return;
    try {
      const response = await apiFetch<DashboardData | { status: string; data: DashboardData }>("/dashboard/summary", {
        token,
        projectId,
      });
      const result = "data" in response ? response.data : response;
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  // Optional polling
  useEffect(() => {
    if (pollInterval > 0 && token && projectId) {
      intervalRef.current = setInterval(fetchSummary, pollInterval);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchSummary, pollInterval, token, projectId]);

  return { data, loading, error, refresh: fetchSummary };
}
