import { z } from "zod";

export const ALLOWED_FILE_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/markdown",
  "text/csv",
  "image/png",
  "image/jpeg",
  "image/tiff",
  "image/bmp",
  "image/webp",
] as const;

export const MAX_FILE_SIZE = 25 * 1024 * 1024;

// Document schemas
export const DocumentUploadSchema = z.object({
  filename: z.string().min(1, "Filename is required"),
  fileType: z.enum(ALLOWED_FILE_TYPES).refine(
    (val) => ALLOWED_FILE_TYPES.includes(val),
    { message: "File type not allowed. Accepted: PDF, DOCX, TXT, images" }
  ),
  size: z.number().max(MAX_FILE_SIZE, "File exceeds 25MB limit"),
});

export const DocumentStatusSchema = z.enum([
  "pending",
  "processing",
  "processed",
  "failed",
]);

export const DocumentSchema = z.object({
  id: z.string(),
  filename: z.string(),
  fileType: z.string(),
  status: DocumentStatusSchema,
  pageCount: z.number().nullable().optional(),
  chunkCount: z.number().nullable().optional(),
  errorMessage: z.string().nullable().optional(),
  uploadedAt: z.string(),
  processedAt: z.string().nullable().optional(),
});

export const DocumentListSchema = z.object({
  documents: z.array(DocumentSchema),
});

// Chat schemas
export const ChatMessageSchema = z.object({
  role: z.enum(["user", "assistant", "system"]),
  content: z.string().min(1, "Message cannot be empty"),
  citations: z.array(z.any()).optional(),
  createdAt: z.string().optional(),
});

export const ChatSessionSchema = z.object({
  id: z.string(),
  title: z.string().nullable().optional(),
  createdAt: z.string(),
});

export const ChatSessionListSchema = z.object({
  sessions: z.array(ChatSessionSchema),
});

// Agent schemas
export const AgentTypeSchema = z.enum(["summarizer", "extractor", "qa", "reviewer"]);

export const AgentSchema = z.object({
  id: z.string(),
  name: z.string().min(1, "Agent name is required"),
  type: AgentTypeSchema,
  config: z.record(z.any()).optional(),
  status: z.enum(["active", "inactive", "error"]),
  createdAt: z.string().nullable().optional(),
});

export const AgentListSchema = z.object({
  agents: z.array(AgentSchema),
});

export const AgentRunSchema = z.object({
  input: z.record(z.any()).optional(),
});

// MCP schemas
export const MCPDirectionSchema = z.enum(["sender", "receiver"]);

export const MCPConnectionSchema = z.object({
  id: z.string(),
  direction: MCPDirectionSchema,
  name: z.string().min(1, "Connection name is required"),
  endpointUrl: z.string().url("Invalid URL").nullable().optional(),
  authConfig: z.record(z.any()).optional(),
  status: z.enum(["connected", "disconnected", "error"]),
});

export const MCPConnectionCreateSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  direction: MCPDirectionSchema,
  endpointUrl: z.string().url("Invalid URL").nullable().optional(),
  authConfig: z.record(z.any()).optional(),
});

// Dashboard schemas
export const DashboardSummarySchema = z.object({
  documents: z.object({
    pending: z.number(),
    processing: z.number(),
    processed: z.number(),
    failed: z.number(),
  }),
  total_documents: z.number(),
  total_entities: z.number(),
  total_relationships: z.number(),
  total_chats: z.number(),
  active_agents: z.number(),
  recent_activity: z.array(z.object({
    id: z.string(),
    action: z.string(),
    resource_type: z.string(),
    resource_id: z.string().nullable().optional(),
    created_at: z.string().nullable().optional(),
  })),
  failed_documents: z.array(z.object({
    id: z.string(),
    filename: z.string(),
    error_message: z.string().nullable().optional(),
    uploaded_at: z.string().nullable().optional(),
  })),
  pipeline_health: z.object({
    queue_depth: z.number(),
    failed_count: z.number(),
    success_rate: z.number(),
  }),
});

// Graph schemas
export const GraphNodeSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.string(),
  description: z.string().optional(),
});

export const GraphEdgeSchema = z.object({
  id: z.string(),
  source: z.string(),
  target: z.string(),
  relation_type: z.string(),
  description: z.string().optional(),
  confidence: z.number().optional(),
});

export const GraphDataSchema = z.object({
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
});

// Search schemas
export const SearchQuerySchema = z.object({
  query: z.string().min(1, "Search query is required").max(500),
  topK: z.number().min(1).max(20).optional().default(8),
});

// Entity schemas
export const EntitySchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.string(),
  description: z.string().nullable().optional(),
  mentionsCount: z.number().optional(),
  relationships: z.array(z.any()).optional(),
});

// Export types
export type DocumentUpload = z.infer<typeof DocumentUploadSchema>;
export type Document = z.infer<typeof DocumentSchema>;
export type DocumentStatus = z.infer<typeof DocumentStatusSchema>;
export type ChatMessage = z.infer<typeof ChatMessageSchema>;
export type ChatSession = z.infer<typeof ChatSessionSchema>;
export type Agent = z.infer<typeof AgentSchema>;
export type MCPConnection = z.infer<typeof MCPConnectionSchema>;
export type DashboardSummary = z.infer<typeof DashboardSummarySchema>;
export type GraphNode = z.infer<typeof GraphNodeSchema>;
export type GraphEdge = z.infer<typeof GraphEdgeSchema>;
export type Entity = z.infer<typeof EntitySchema>;
