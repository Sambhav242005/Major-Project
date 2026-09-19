/**
 * Centralized TypeScript types for the AKGB frontend.
 *
 * Most domain types are defined as Zod schemas in `./validators.ts` and
 * re-exported here for convenience. Additional ad-hoc types that don't
 * need runtime validation live directly in this file.
 */

// Re-export all validated domain types
export type {
  DocumentUpload,
  Document,
  DocumentStatus,
  ChatMessage,
  ChatSession,
  Agent,
  MCPConnection,
  DashboardSummary,
  GraphNode,
  GraphEdge,
  Entity,
} from "./validators";

export { ALLOWED_FILE_TYPES, MAX_FILE_SIZE } from "./validators";

// Re-export Project from store (single source of truth)
export type { Project } from "@/stores/project";

// --- Ad-hoc types (no Zod schema needed) ---

/** Document detail with chunk metadata (documents/[id] page) */
export interface DocumentDetail {
  id: string;
  filename: string;
  file_type: string;
  status: string;
  page_count: number | null;
  error_message: string | null;
  uploaded_at: string | null;
  processed_at: string | null;
}

/** A text chunk belonging to a document */
export interface Chunk {
  id: string;
  chunk_index: number;
  page_number: number | null;
  text: string;
  token_count: number | null;
}

/** Agent search result (agents page) */
export interface SearchResults {
  chunks: Array<{
    id: string;
    text: string;
    document_id: string;
    score: number;
    metadata: Record<string, unknown>;
  }>;
}

/** Entity detail with full metadata (agents page sidebar) */
export interface EntityDetail {
  id: string;
  name: string;
  type: string;
  description: string | null;
  mentions_count?: number;
  relationships?: Array<{
    id: string;
    name: string;
    type: string;
    relation_type: string;
    confidence?: number;
  }>;
  mentions?: Array<{
    document_id: string;
    filename: string;
    chunk_id: string;
    context: string;
    created_at: string;
  }>;
}

/** Meeting analysis result */
export interface MeetingAnalysis {
  filename?: string;
  transcript: string;
  summary: string;
  key_points: string[];
  action_items: string[];
  sentiment: string;
  sentiment_reason?: string;
}

/** Webhook subscription */
export interface WebhookSubscription {
  id: string;
  event_type: string;
  url: string;
  active: boolean;
  created_at: string;
}

/** Webhook delivery log entry */
export interface WebhookDelivery {
  id: string;
  event_type: string;
  success: boolean;
  attempts: number;
  response_status: number | null;
  created_at: string;
}

/** MCP connection with raw API field names */
export interface MCPConnectionRaw {
  id: string;
  direction: "sender" | "receiver";
  name: string;
  endpoint_url: string | null;
  auth_config: Record<string, unknown>;
  status: string;
}

/** Dashboard API response shape */
export interface DashboardData {
  documents: {
    pending: number;
    processing: number;
    processed: number;
    failed: number;
  };
  total_documents: number;
  total_entities: number;
  total_relationships: number;
  total_chats: number;
  active_agents: number;
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

/** Graph data with edges using `relation_type` field */
export interface GraphData {
  nodes: Array<{ id: string; label?: string; [key: string]: unknown }>;
  edges: Array<{ id: string; source: string; target: string; label?: string; [key: string]: unknown }>;
}

/** Entity relationship in graph store (uses `label` instead of `relation_type`) */
export interface GraphEdgeLabel {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence?: number;
}
