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
    async (payload: { direction: "sender" | "receiver"; name: string; endpoint_url: string; auth_config?: Record<string, unknown> }) => {
      if (!token || !projectId) throw new Error("Select a project and sign in first.");
      try {
      const { connection: conn } = await apiFetch<{ connection: MCPConnectionRaw }>("/mcp/connections", {
          method: "POST",
          token,
          projectId,
          body: payload,
        });
        setConnections((prev) => [...prev, conn]);
        return conn;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to create connection");
        throw e;
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
        const { connection: updated } = await apiFetch<{ connection: MCPConnectionRaw }>(`/mcp/connections/${connectionId}`, {
          method: "PATCH", token, projectId, body: payload,
        });
        setConnections((prev) => prev.map((c) => c.id === connectionId ? updated : c));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update connection");
        throw e;
      }
    }, [token, projectId]
  );

  const syncConnection = useCallback(async (connectionId: string) => {
    if (!token || !projectId) throw new Error("Select a project and sign in first.");
    try {
      const result = await apiFetch<{ status: string; protocol_version: string; tool_count: number | null }>(`/mcp/connections/${connectionId}/test`, { method: "POST", token, projectId, timeoutMs: 45000 });
      setConnections((prev) => prev.map((connection) => connection.id === connectionId ? { ...connection, status: result.status } : connection));
      setError(null);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection test failed");
      throw e;
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
    refresh: fetchConnections,
  };
}
