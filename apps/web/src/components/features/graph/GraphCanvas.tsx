"use client";

import Link from "next/link";
import {
  GraphCanvas as ReagraphCanvas,
  GraphEdge,
  GraphNode,
} from "reagraph";

interface GraphCanvasWrapperProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: any) => void;
  loading?: boolean;
  empty?: boolean;
  emptyMessage?: string;
  viewerKey?: number;
}

export function GraphCanvas({
  nodes,
  edges,
  onNodeClick,
  loading = false,
  empty = false,
  emptyMessage,
  viewerKey = 0,
}: GraphCanvasWrapperProps) {
  if (loading) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-app-bg/80 z-10">
        <p className="text-app-muted">Loading graph...</p>
      </div>
    );
  }

  if (empty) {
    return (
      <div className="absolute inset-0 flex items-center justify-center z-10">
        <div className="text-center">
          <p className="text-app-text font-medium mb-1">No entities yet</p>
          {emptyMessage && (
            <p className="text-app-muted text-sm">{emptyMessage}</p>
          )}
          <Link href="/documents" className="inline-block mt-4">
            <span className="px-4 py-2 rounded-lg bg-brand-accent/15 text-app-text border border-brand-accent/25 text-sm font-medium hover:bg-brand-accent/25 transition-all">
              Upload Documents
            </span>
          </Link>
        </div>
      </div>
    );
  }

  if (nodes.length === 0) return null;

  return (
    <ReagraphCanvas
      key={viewerKey}
      nodes={nodes}
      edges={edges}
      onNodeClick={onNodeClick}
      layoutType="forceDirected2d"
      edgeArrowPosition="none"
      labelType="auto"
      sizingType="attribute"
      edgeLabelPosition="inline"
    />
  );
}
