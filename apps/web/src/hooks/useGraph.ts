/**
 * Knowledge graph: fetch nodes/edges, search, select entities.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import { GraphNode, GraphEdge } from "@/lib/validators";

interface UseGraphOptions {
  token: string | null;
  projectId: string | null;
}

export function useGraph({ token, projectId }: UseGraphOptions) {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const fetchGraph = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    try {
      const data = await apiFetch<{ nodes: GraphNode[]; edges: GraphEdge[] }>(
        "/graph",
        { token, projectId }
      );
      setNodes(data.nodes ?? []);
      setEdges(data.edges ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const search = useCallback(
    async (query: string) => {
      if (!token || !projectId || !query.trim()) {
        fetchGraph();
        return;
      }
      setLoading(true);
      try {
        const data = await apiFetch<{ nodes: GraphNode[]; edges: GraphEdge[] }>(
          `/graph/search?q=${encodeURIComponent(query)}`,
          { token, projectId }
        );
        setNodes(data.nodes ?? []);
        setEdges(data.edges ?? []);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Search failed");
      } finally {
        setLoading(false);
      }
    },
    [token, projectId, fetchGraph]
  );

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;

  return {
    nodes,
    edges,
    loading,
    error,
    selectedNodeId,
    selectedNode,
    searchQuery,
    setSelectedNodeId,
    setSearchQuery,
    search,
    refresh: fetchGraph,
  };
}
