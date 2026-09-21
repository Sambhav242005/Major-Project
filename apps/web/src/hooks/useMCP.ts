/**
 * MCP connections: list, create, update, delete.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import type { MCPConnectionRaw } from "@/lib/types";

interface UseMCPOptions {
  token: string | null;
  projectId: string | null;
}

export function useMCP({ token, projectId }: UseMCPOptions) {
  const [connections, setConnections] = useState<MCPConnectionRaw[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConnections = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    try {
      const response = await apiFetch<MCPConnectionRaw[] | { connections: MCPConnectionRaw[] }>("/mcp/connections", {
        token,
        projectId,
      });
      setConnections(Array.isArray(response) ? response : response.connections ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load connections");
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  const createConnection = useCallback(
    async (payload: { name: string; endpoint_url: string; auth_config?: Record<string, unknown> }) => {
      if (!token || !projectId) return null;
      try {
      const conn = await apiFetch<MCPConnectionRaw>("/mcp/connections", {
          method: "POST",
          token,
          projectId,
          body: payload,
        });
        setConnections((prev) => [...prev, conn]);
        return conn;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to create connection");
        return null;
      }
    },
    [token, projectId]
  );

  const deleteConnection = useCallback(
    async (connectionId: string) => {
      if (!token || !projectId) return;
      try {
        await apiFetch(`/mcp/connections/${connectionId}`, {
          method: "DELETE",
          token,
          projectId,
        });
        setConnections((prev) => prev.filter((c) => c.id !== connectionId));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to delete connection");
      }
    },
    [token, projectId]
  );

  const updateConnection = useCallback(
    async (connectionId: string, payload: Partial<MCPConnectionRaw>) => {
      if (!token || !projectId) return;
      try {
        const updated = await apiFetch<MCPConnectionRaw>(`/mcp/connections/${connectionId}`, {
          method: "PATCH", token, projectId, body: payload,
        });
        setConnections((prev) => prev.map((c) => c.id === connectionId ? updated : c));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update connection");
      }
    }, [token, projectId]
  );

  const syncConnection = useCallback(async (connectionId: string) => {
    if (!token || !projectId) return;
    try {
      await apiFetch(`/mcp/connections/${connectionId}/sync`, { method: "POST", token, projectId });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
    }
  }, [token, projectId]);

  const syncMeetings = useCallback(async () => {
    if (!token || !projectId) return;
    try {
      await apiFetch("/meetings/sync", { method: "POST", token, projectId, body: { source: "google_meet" } });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
    }
  }, [token, projectId]);

  return {
    connections,
    loading,
    error,
    createConnection,
    updateConnection,
    deleteConnection,
    syncConnection,
    syncMeetings,
    refresh: fetchConnections,
  };
}
