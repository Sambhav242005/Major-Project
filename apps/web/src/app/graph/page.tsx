"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useGraphStore } from "@/stores/graph";

const ENTITY_COLORS: Record<string, string> = {
  PERSON: "#d97706",
  ORG: "#16a34a",
  GPE: "#64748b",
  EVENT: "#dc2626",
  CONCEPT: "#1e293b",
};

function EntityNode({ data }: { data: { label: string; type: string; description?: string } }) {
  const color = ENTITY_COLORS[data.type] || "#64748b";
  return (
    <div
      className="px-4 py-2 rounded-lg border-2 shadow-sm bg-white cursor-pointer hover:shadow-md transition-shadow"
      style={{ borderColor: color }}
    >
      <div className="text-xs font-mono text-slate mb-0.5">{data.type}</div>
      <div className="font-medium text-ink text-sm">{data.label}</div>
    </div>
  );
}

const nodeTypes = { entityNode: EntityNode };

export default function GraphPage() {
  const supabase = createClient();
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
  } = useGraphStore();

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState([]);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState([]);
  const [selectedEntity, setSelectedEntity] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Convert store data to React Flow format
  useEffect(() => {
    const nodes: Node[] = storeNodes.map((n, i) => ({
      id: n.id,
      type: "entityNode",
      position: { x: (i % 5) * 200, y: Math.floor(i / 5) * 120 },
      data: { label: n.name, type: n.type, description: n.description },
    }));

    const edges: Edge[] = storeEdges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      type: "smoothstep",
      animated: true,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { strokeWidth: 2, stroke: "#94a3b8" },
    }));

    setRfNodes(nodes);
    setRfEdges(edges);
  }, [storeNodes, storeEdges, setRfNodes, setRfEdges]);

  // Fetch graph data
  const fetchGraph = useCallback(
    async (entityId?: string) => {
      setLoading(true);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const params = new URLSearchParams({ depth: String(depth) });
        if (entityId) params.set("entity_id", entityId);

        const res = await fetch(
          `http://localhost:8000/kb/graph?${params}`,
          { headers: { Authorization: `Bearer ${session.access_token}` } }
        );

        if (res.ok) {
          const data = await res.json();
          setGraphData(data.nodes || [], data.edges || []);
        }
      } catch (e) {
        console.error("Failed to fetch graph:", e);
      } finally {
        setLoading(false);
      }
    },
    [depth, setGraphData, supabase]
  );

  // Fetch entity detail when selected
  const fetchEntity = useCallback(
    async (entityId: string) => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) return;

        const res = await fetch(
          `http://localhost:8000/kb/entities/${entityId}`,
          { headers: { Authorization: `Bearer ${session.access_token}` } }
        );

        if (res.ok) {
          const data = await res.json();
          setSelectedEntity(data.entity);
        }
      } catch (e) {
        console.error("Failed to fetch entity:", e);
      }
    },
    [supabase]
  );

  // Load graph on mount
  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // Handle node click
  const onNodeClick = useCallback(
    (_: any, node: Node) => {
      selectEntity(node.id);
      fetchEntity(node.id);
    },
    [selectEntity, fetchEntity]
  );

  // Handle depth change
  const handleDepthChange = (newDepth: number) => {
    setDepth(newDepth);
    fetchGraph(selectedEntityId || undefined);
  };

  // Handle search
  const handleSearch = () => {
    // Search for entity by name, then center graph on it
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
    <div className="min-h-screen bg-paper">
      <header className="border-b border-slate/20 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-slate hover:text-ink transition-colors">
              ← Dashboard
            </Link>
            <h1 className="font-display text-xl font-semibold text-ink">
              Knowledge Graph Explorer
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/documents" className="text-sm text-slate hover:text-ink transition-colors">
              Documents
            </Link>
            <Link href="/chat" className="text-sm text-slate hover:text-ink transition-colors">
              Chat
            </Link>
            <Link href="/agents" className="text-sm text-slate hover:text-ink transition-colors">
              Agents
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

      <div className="flex h-[calc(100vh-64px)]">
        {/* Controls Panel */}
        <div className="w-72 border-r border-slate/20 bg-white p-4 flex flex-col gap-4 overflow-y-auto">
          {/* Search */}
          <div>
            <label className="text-sm font-medium text-ink mb-1 block">Search Entity</label>
            <div className="flex gap-2">
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Entity name..."
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
              <Button onClick={handleSearch} size="sm">Go</Button>
            </div>
          </div>

          {/* Depth Slider */}
          <div>
            <label className="text-sm font-medium text-ink mb-1 block">
              Depth: {depth}
            </label>
            <input
              type="range"
              min={1}
              max={3}
              value={depth}
              onChange={(e) => handleDepthChange(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate mt-1">
              <span>1</span>
              <span>2</span>
              <span>3</span>
            </div>
          </div>

          {/* Refresh */}
          <Button
            onClick={() => fetchGraph(selectedEntityId || undefined)}
            variant="outline"
            disabled={loading}
          >
            {loading ? "Loading..." : "Refresh Graph"}
          </Button>

          {/* Entity Detail Panel */}
          {selectedEntity && (
            <Card className="mt-2">
              <CardHeader className="pb-2">
                <CardTitle className="font-display text-base">
                  {selectedEntity.name}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Badge className={ENTITY_COLORS[selectedEntity.type] ? "text-white" : ""}>
                  {selectedEntity.type}
                </Badge>
                {selectedEntity.description && (
                  <p className="text-sm text-slate">{selectedEntity.description}</p>
                )}
                <div className="text-xs text-slate">
                  Mentions: {selectedEntity.mentions_count}
                </div>
                {selectedEntity.relationships?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-ink mb-1">Relationships</p>
                    <div className="space-y-1">
                      {selectedEntity.relationships.map((rel: any) => (
                        <div key={rel.id} className="text-xs text-slate">
                          <span className="text-ink">{rel.other_entity_name}</span>
                          {" "}
                          <span className="text-slate">({rel.relation_type})</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Legend */}
          <div className="mt-auto">
            <p className="text-xs font-medium text-ink mb-2">Legend</p>
            <div className="space-y-1">
              {Object.entries(ENTITY_COLORS).map(([type, color]) => (
                <div key={type} className="flex items-center gap-2 text-xs">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: color }} />
                  <span className="text-slate">{type}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Graph Canvas */}
        <div className="flex-1 relative">
          {loading && storeNodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center bg-paper/80 z-10">
              <p className="text-slate">Loading graph...</p>
            </div>
          )}
          {!loading && storeNodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <p className="text-ink font-medium mb-1">No entities yet</p>
                <p className="text-slate text-sm">
                  Upload documents to start building the knowledge graph
                </p>
                <Link href="/documents">
                  <Button className="mt-4" variant="outline">Upload Documents</Button>
                </Link>
              </div>
            </div>
          )}
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-left"
          >
            <Background />
            <Controls />
            <MiniMap
              nodeColor={(node) => {
                const type = node.data?.type;
                return ENTITY_COLORS[type] || "#64748b";
              }}
            />
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}
