"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { apiFetch } from "@/lib/api/client";
import Link from "next/link";
import { GraphCanvas, GraphEdge, GraphNode, useSelection } from "reagraph";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useGraphStore } from "@/stores/graph";
import { useProjectStore } from "@/stores/project";
import { DashboardHeader } from "@/components/dashboard-header";

const ENTITY_COLORS: Record<string, string> = {
  PERSON: "#f59e0b",
  ORG: "#22c55e",
  GPE: "#64748b",
  EVENT: "#ef4444",
  CONCEPT: "#38bdf8",
};

export default function GraphPage() {
  return <GraphPageInner />;
}

function GraphPageInner() {
  const supabaseRef = useRef(createClient());
  const supabase = supabaseRef.current;
  const {
    nodes: storeNodes,
    edges: storeEdges,
    selectedEntityId,
    searchQuery,
    depth,
    setGraphData,
    selectEntity,
    setSearchQuery,
    setDepth,
    clearGraph,
  } = useGraphStore();
  const { projects, activeProjectId, loadProjects } = useProjectStore();
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<any>(null);
  const [entityChunks, setEntityChunks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string[]>([]);
  const [viewerKey, setViewerKey] = useState(0);
  const canvasRef = useRef<{ zoomIn?: () => void; zoomOut?: () => void; fit?: () => void } | null>(null);

  const entityTypes = Array.from(new Set(storeNodes.map((n: any) => n.type)));

  const toggleType = useCallback((type: string) => {
    setTypeFilter((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  }, []);

  const fetchGraph = useCallback(
    async (entityId?: string) => {
      setLoading(true);
      setError(null);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const params = new URLSearchParams({ depth: String(depth) });
        if (entityId) params.set("entity_id", entityId);

        const data = await apiFetch<{ nodes: any[]; edges: any[] }>(
          `/kb/graph?${params}`,
          { token: session.access_token, projectId: activeProjectId }
        );

        const apiNodes = data.nodes || [];
        const apiEdges = data.edges || [];

        // Entity-type filter (progressive disclosure — cut hairball, not data)
        const active = typeFilter.length === 0 ? null : typeFilter;
        const visibleNodes = active ? apiNodes.filter((n: any) => active.includes(n.type)) : apiNodes;
        const visibleIds = new Set(visibleNodes.map((n: any) => n.id));
        const visibleEdges = apiEdges.filter(
          (e: any) => visibleIds.has(e.source) && visibleIds.has(e.target)
        );

        const nodes: GraphNode[] = visibleNodes.map((n: any) => ({
          id: n.id,
          label: n.name,
          fill: ENTITY_COLORS[n.type] || "#64748b",
          size: 8,
        }));

        const edges: GraphEdge[] = visibleEdges.map((e: any) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.relation_type || "",
        }));

        setGraphData(apiNodes, apiEdges);
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
    [depth, typeFilter, setGraphData, activeProjectId]
  );

  const fetchEntity = useCallback(
    async (entityId: string) => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const [entityRes, chunksRes] = await Promise.all([
          apiFetch<{ entity: any }>(`/kb/entities/${entityId}`, {
            token: session.access_token,
            projectId: activeProjectId,
          }),
          apiFetch<{ chunks: any[] }>(`/kb/entities/${entityId}/chunks`, {
            token: session.access_token,
            projectId: activeProjectId,
          }),
        ]);
        setSelectedEntity(entityRes.entity);
        // Dedupe chunks by filename+page — the same section can be stored
        // as multiple chunk rows (e.g. after re-processing a document), so
        // keying on chunk_id would still show duplicates.
        const seen = new Set<string>();
        const uniqueChunks = (chunksRes.chunks || []).filter((c: any) => {
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

  // Load project list once; re-fetch graph when the active project changes
  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      if (!projects.length) await loadProjects(session.access_token);
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const handleNodeClick = useCallback(
    (node: any) => {
      const nodeId = node?.id || node;
      selectEntity(nodeId);
      fetchEntity(nodeId);
    },
    [selectEntity, fetchEntity]
  );

  const handleDepthChange = (newDepth: number) => {
    setDepth(newDepth);
    fetchGraph(selectedEntityId || undefined);
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
        {/* Sidebar toggle */}
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          aria-expanded={sidebarOpen}
          aria-label={sidebarOpen ? "Collapse panel" : "Expand panel"}
          className="w-8 shrink-0 border-r border-app-border bg-app-surface-alt flex items-center justify-center text-app-muted hover:text-app-text transition-colors"
        >
          {sidebarOpen ? "«" : "»"}
        </button>

        {/* Controls Panel */}
        {sidebarOpen && (
        <div className="w-72 shrink-0 border-r border-app-border bg-app-surface-alt p-4 flex flex-col gap-4 overflow-y-auto scrollbar-dark transition-all">
          <div>
            <label className="text-xs text-app-muted uppercase tracking-wider mb-1.5 block">Search Entity</label>
            <div className="flex gap-2">
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Entity name..."
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="flex-1 h-9 px-3 rounded-lg bg-app-surface-alt border border-app-border-strong text-sm text-app-text placeholder:text-app-muted outline-none focus:border-brand-accent/50 transition-all"
              />
              <button onClick={handleSearch} className="h-9 px-3 rounded-lg bg-brand-accent/15 text-app-text border border-brand-accent/25 text-sm font-medium hover:bg-brand-accent/25 transition-all">
                Go
              </button>
            </div>
          </div>

          {/* Entity-type filter chips */}
          {entityTypes.length > 0 && (
            <div>
              <label className="text-xs text-app-muted uppercase tracking-wider mb-1.5 block">
                Filter by type {typeFilter.length > 0 && `(${typeFilter.length})`}
              </label>
              <div className="flex flex-wrap gap-1.5">
                {entityTypes.map((type) => (
                  <button
                    key={type}
                    onClick={() => toggleType(type)}
                    aria-pressed={typeFilter.includes(type)}
                    className={`text-[11px] px-2 py-1 rounded-full border transition-colors ${
                      typeFilter.includes(type)
                        ? "bg-brand-accent/20 border-brand-accent/40 text-app-text"
                        : "bg-app-surface border-app-border-strong text-app-muted hover:text-app-text"
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="text-xs text-app-muted uppercase tracking-wider mb-1.5 block">
              Depth: {depth}
            </label>
            <input
              type="range"
              min={1}
              max={3}
              value={depth}
              onChange={(e) => handleDepthChange(Number(e.target.value))}
              className="w-full accent-brand-accent"
            />
            <div className="flex justify-between text-xs text-app-muted mt-1">
              <span>1</span>
              <span>2</span>
              <span>3</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => fetchGraph(selectedEntityId || undefined)}
              disabled={loading}
              className="h-9 px-3 rounded-lg bg-app-surface text-app-text border border-app-border-strong text-sm font-medium hover:bg-app-card-hover disabled:opacity-40 transition-all"
            >
              {loading ? "Loading..." : "Refresh"}
            </button>
            <button
              onClick={() => setViewerKey((k) => k + 1)}
              className="h-9 px-3 rounded-lg bg-app-surface text-app-text border border-app-border-strong text-sm font-medium hover:bg-app-card-hover transition-all"
            >
              Fit view
            </button>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          {selectedEntity && (
            <div className="glow-card p-4 mt-2">
              <h3 className="text-sm font-medium text-app-text mb-2">
                {selectedEntity.name}
              </h3>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded inline-block mb-2"
                style={{
                  background: `${ENTITY_COLORS[selectedEntity.type]}20`,
                  color: ENTITY_COLORS[selectedEntity.type],
                  border: `1px solid ${ENTITY_COLORS[selectedEntity.type]}40`,
                }}
              >
                {selectedEntity.type}
              </span>
              {selectedEntity.description && (
                <p className="text-xs text-app-muted mb-2">{selectedEntity.description}</p>
              )}
              <div className="text-[10px] text-app-muted">
                Mentions: {selectedEntity.mentions_count}
              </div>
              {selectedEntity.relationships?.length > 0 && (
                <div className="mt-3">
                  <p className="text-[10px] text-app-muted uppercase tracking-wider mb-1">Relationships</p>
                  <div className="space-y-1">
                    {selectedEntity.relationships.map((rel: any) => (
                      <div key={rel.id} className="text-[11px] text-app-muted">
                        <span className="text-app-text">{rel.other_entity_name}</span>
                        {" "}
                        <span className="text-app-muted">({rel.relation_type})</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {selectedEntity && entityChunks.length > 0 && (
            <div className="mt-2">
              <p className="text-[10px] text-app-muted uppercase tracking-wider mb-2">
                Source sections ({entityChunks.length})
              </p>
              <div className="space-y-2">
                {entityChunks.map((chunk: any, idx: number) => (
                  <div
                    key={chunk.chunk_id ?? idx}
                    className="rounded-lg border border-app-border bg-app-surface p-2.5"
                  >
                    <div className="flex items-center justify-between mb-1 gap-2">
                      <span className="text-[10px] font-mono text-app-muted truncate">
                        {chunk.filename}
                      </span>
                      <span className="text-[10px] font-mono text-app-muted shrink-0">
                        p.{chunk.page_number ?? "?"}
                      </span>
                    </div>
                    <p className="text-[11px] leading-relaxed text-app-text line-clamp-4">
                      {chunk.text}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-auto">
            <p className="text-[10px] text-app-muted uppercase tracking-wider mb-2">Legend</p>
            <div className="space-y-1.5">
              {Object.entries(ENTITY_COLORS).map(([type, color]) => (
                <div key={type} className="flex items-center gap-2 text-xs">
                  <div className="w-2.5 h-2.5 rounded" style={{ backgroundColor: color }} />
                  <span className="text-app-muted">{type}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        )}

        {/* Graph Canvas */}
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
              layoutType="forceDirected2d"
              edgeArrowPosition="none"
              labelType="auto"
              sizingType="attribute"
              edgeLabelPosition="inline"
            />
          )}
        </div>
      </div>
    </div>
  );
}
