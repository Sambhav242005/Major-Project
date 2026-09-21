"use client";

import { useCallback, useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch } from "@/lib/api/client";
import Link from "next/link";
import type { GraphEdge as ReagraphEdge, GraphNode as ReagraphNode } from "reagraph";
import { useGraphStore } from "@/stores/graph";
import { useProjectStore } from "@/stores/project";
import type { EntityChunk, EntityDetail } from "@/lib/types";
import { DashboardHeader } from "@/components/layout/dashboard-header";
import { GraphCanvas, GraphSearch, GraphTypeFilter, GraphControls, EntityDetailPanel, GraphLegend } from "@/components/features/graph";

const ENTITY_COLORS: Record<string, string> = {
  PERSON: "#f59e0b",
  ORG: "#22c55e",
  GPE: "#64748b",
  EVENT: "#ef4444",
  CONCEPT: "#38bdf8",
};

interface ApiGraphNode {
  id: string;
  name: string;
  type: string;
  description: string | null;
}

interface ApiGraphEdge {
  id: string;
  source: string;
  target: string;
  relation_type: string;
  description: string | null;
  confidence: number;
}

interface ApiGraphResponse {
  nodes: ApiGraphNode[];
  edges: ApiGraphEdge[];
}


interface ApiGraphNode {
  id: string;
  name: string;
  type: string;
  description: string | null;
}

interface ApiGraphEdge {
  id: string;
  source: string;
  target: string;
  relation_type: string;
  description: string | null;
  confidence: number;
}

interface ApiGraphResponse {
  nodes: ApiGraphNode[];
  edges: ApiGraphEdge[];
}


export default function GraphPage() {
  const [supabase] = useState(() => createClient());

  const {
    nodes: storeNodes,
    selectedEntityId,
    searchQuery,
    depth,
    setGraphData,
    selectEntity,
    setDepth,
    clearGraph,
  } = useGraphStore();
  const { projects, activeProjectId, loadProjects } = useProjectStore();
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  const [graphNodes, setGraphNodes] = useState<ReagraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<ReagraphEdge[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<EntityDetail | null>(null);
  const [entityChunks, setEntityChunks] = useState<EntityChunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string[]>([]);
  const [viewerKey, setViewerKey] = useState(0);

  const entityTypes = Array.from(new Set(storeNodes.map((n) => n.type)));

  const toggleType = useCallback((type: string) => {
    setTypeFilter((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  }, []);

  const fetchGraph = useCallback(
    async (entityId?: string, depthOverride = depth) => {
      setLoading(true);
      setError(null);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const params = new URLSearchParams({ depth: String(depthOverride) });
        if (entityId) params.set("entity_id", entityId);

        const data = await apiFetch<ApiGraphResponse>(
          `/kb/graph?${params}`,
          { token: session.access_token, projectId: activeProjectId }
        );

        const apiNodes = data.nodes || [];
        const apiEdges = data.edges || [];

        const active = typeFilter.length === 0 ? null : typeFilter;
        const visibleNodes = active ? apiNodes.filter((n) => active.includes(n.type)) : apiNodes;
        const visibleIds = new Set(visibleNodes.map((n) => n.id));
        const visibleEdges = apiEdges.filter(
          (e) => visibleIds.has(e.source) && visibleIds.has(e.target)
        );

        const nodes: ReagraphNode[] = visibleNodes.map((n) => ({
          id: n.id,
          label: n.name,
          fill: ENTITY_COLORS[n.type] || "#64748b",
          size: 8,
        }));

        const edges: ReagraphEdge[] = visibleEdges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.relation_type || "",
        }));

        setGraphData(
          apiNodes.map((node) => ({
            ...node,
            description: node.description ?? undefined,
          })),
          apiEdges.map((edge) => ({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.relation_type,
            confidence: edge.confidence,
          }))
        );
        setGraphNodes(nodes);
        setGraphEdges(edges);
      } catch (e) {
        setError(
          e instanceof Error ? e.message : "Failed to connect to server"
        );
      } finally {
        setLoading(false);
      }
    },
    [depth, typeFilter, setGraphData, activeProjectId, supabase.auth]
  );

  const fetchEntity = useCallback(
    async (entityId: string) => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const [entityRes, chunksRes] = await Promise.all([
          apiFetch<{ entity: EntityDetail }>(`/kb/entities/${entityId}`, {
            token: session.access_token,
            projectId: activeProjectId,
          }),
          apiFetch<{ chunks: EntityChunk[] }>(`/kb/entities/${entityId}/chunks`, {
            token: session.access_token,
            projectId: activeProjectId,
          }),
        ]);
        setSelectedEntity(entityRes.entity);
        const seen = new Set<string>();
        const uniqueChunks = (chunksRes.chunks || []).filter((c) => {
          const key = `${c.filename}|${c.page_number ?? 0}`;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
        setEntityChunks(uniqueChunks);
      } catch (e) {
        console.error("Failed to fetch entity:", e);
        setSelectedEntity(null);
        setEntityChunks([]);
      }
    },
    [supabase, activeProjectId]
  );

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      if (!projects.length) await loadProjects(session.access_token);
    };
    init();
  }, [loadProjects, projects.length, supabase.auth]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const handleNodeClick = useCallback(
    (node: ReagraphNode) => {
      const nodeId = node.id;
      selectEntity(nodeId);
      fetchEntity(nodeId);
    },
    [selectEntity, fetchEntity]
  );

  const handleDepthChange = (newDepth: number) => {
    setDepth(newDepth);
    void fetchGraph(selectedEntityId || undefined, newDepth);
  };

  const handleSearch = () => {
    const match = storeNodes.find(
      (n) => n.name.toLowerCase() === searchQuery.toLowerCase()
    );
    if (match) {
      selectEntity(match.id);
      fetchGraph(match.id);
      fetchEntity(match.id);
    }
  };

  return (
    <div className="min-h-screen bg-app-bg text-app-text">
      <DashboardHeader title="Knowledge Graph Explorer" showBack backHref="/dashboard" />

      <div className="border-b border-app-border bg-app-surface-alt/50 px-6 py-2 flex items-center gap-3 text-sm">
        <span className="text-app-muted">Project:</span>
        <span className="font-medium text-app-text">{activeProject?.name ?? "—"}</span>
        <span className="flex-1" />
        <button
          onClick={clearGraph}
          disabled={storeNodes.length === 0}
          className="text-xs px-3 py-1.5 rounded-lg bg-app-surface border border-app-border-strong text-app-muted hover:text-app-text transition-colors disabled:opacity-40"
        >
          Clear graph
        </button>
      </div>

      <div className="flex h-[calc(100vh-104px)] overflow-hidden">
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          aria-expanded={sidebarOpen}
          aria-label={sidebarOpen ? "Collapse panel" : "Expand panel"}
          className="w-8 shrink-0 border-r border-app-border bg-app-surface-alt flex items-center justify-center text-app-muted hover:text-app-text transition-colors"
        >
          {sidebarOpen ? "«" : "»"}
        </button>

        {sidebarOpen && (
          <div className="w-72 shrink-0 border-r border-app-border bg-app-surface-alt p-4 flex flex-col gap-4 overflow-y-auto scrollbar-dark transition-all">
            <GraphSearch onSearch={handleSearch} />
            <GraphTypeFilter entityTypes={entityTypes} activeFilters={typeFilter} onToggle={toggleType} />
            <GraphControls
              depth={depth}
              onDepthChange={handleDepthChange}
              onRefresh={() => fetchGraph(selectedEntityId || undefined)}
              onFitView={() => setViewerKey((k) => k + 1)}
              loading={loading}
            />

            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}

            <EntityDetailPanel entity={selectedEntity} chunks={entityChunks} />
            <GraphLegend />
          </div>
        )}

        <div className="flex-1 min-w-0 relative bg-app-bg overflow-hidden">
          {loading && storeNodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center bg-app-bg/80 z-10">
              <p className="text-app-muted">Loading graph...</p>
            </div>
          )}
          {!loading && storeNodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <div className="text-center">
                <p className="text-app-text font-medium mb-1">No entities yet</p>
                <p className="text-app-muted text-sm">
                  {activeProject
                    ? `"${activeProject.name}" has no entities yet — upload documents to start building the graph.`
                    : "Upload documents to start building the knowledge graph"}
                </p>
                <Link href="/documents" className="inline-block mt-4">
                  <span className="px-4 py-2 rounded-lg bg-brand-accent/15 text-app-text border border-brand-accent/25 text-sm font-medium hover:bg-brand-accent/25 transition-all">
                    Upload Documents
                  </span>
                </Link>
              </div>
            </div>
          )}
          {graphNodes.length > 0 && (
            <GraphCanvas
              key={viewerKey}
              nodes={graphNodes}
              edges={graphEdges}
              onNodeClick={handleNodeClick}
              viewerKey={viewerKey}
            />
          )}
        </div>
      </div>
    </div>
  );
}
