import { create } from "zustand";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  description?: string;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence?: number;
}

interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedEntityId: string | null;
  searchQuery: string;
  depth: number;
  setGraphData: (nodes: GraphNode[], edges: GraphEdge[]) => void;
  selectEntity: (id: string | null) => void;
  setSearchQuery: (query: string) => void;
  setDepth: (depth: number) => void;
  clearGraph: () => void;
}

export const useGraphStore = create<GraphState>((set) => ({
  nodes: [],
  edges: [],
  selectedEntityId: null,
  searchQuery: "",
  depth: 2,

  setGraphData: (nodes, edges) => set({ nodes, edges }),

  selectEntity: (id) => set({ selectedEntityId: id }),

  setSearchQuery: (query) => set({ searchQuery: query }),

  setDepth: (depth) => set({ depth }),

  clearGraph: () => set({ nodes: [], edges: [], selectedEntityId: null }),
}));
