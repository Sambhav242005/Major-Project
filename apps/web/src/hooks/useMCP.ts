/**
 * MCP connections: list, create, update, delete.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import { MCPConnection } from "@/lib/validators";

interface UseMCPOptions {
  token: string | null;
  projectId: string | null;
}

export function useMCP({ token, projectId }: UseMCPOptions) {
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConnections = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    try {
      const data = await apiFetch<MCPConnection[]>("/mcp/connections", {
        token,
        projectId,
      });
      setConnections(Array.isArray(data) ? data : []);
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
        const conn = await apiFetch<MCPConnection>("/mcp/connections", {
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

  return {
    connections,
    loading,
    error,
    createConnection,
    deleteConnection,
    refresh: fetchConnections,
  };
}
