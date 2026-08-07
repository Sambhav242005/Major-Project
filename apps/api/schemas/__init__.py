from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


# --- Document Schemas ---

class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: str


class DocumentChunkOut(BaseModel):
    id: str
    chunk_index: int
    page_number: int | None
    text: str
    token_count: int | None


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    page_count: int | None
    error_message: str | None
    uploaded_at: datetime
    processed_at: datetime | None


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    error_message: str | None


# --- Entity Schemas ---

class EntityOut(BaseModel):
    id: str
    name: str
    type: str
    description: str | None
    first_seen_document_id: str | None


class EntityDetailResponse(BaseModel):
    entity: EntityOut
    relationships: list["RelationshipOut"]
    mentions: list["EntityMentionOut"]


class EntityMentionOut(BaseModel):
    id: str
    document_id: str
    chunk_id: str | None
    mention_text: str | None
    confidence: float | None


class RelationshipOut(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    description: str | None
    confidence: float | None


# --- Graph Schemas ---

class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    description: str | None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation_type: str
    description: str | None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# --- Search Schemas ---

class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: int | None
    text: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]


# --- Chat Schemas ---

class ChatSessionCreate(BaseModel):
    title: str | None = None


class ChatSessionOut(BaseModel):
    id: str
    title: str | None
    created_at: datetime


class CitationOut(BaseModel):
    chunk_id: str
    document_id: str
    page_number: int | None
    filename: str | None


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: list[CitationOut] | None
    created_at: datetime


class ChatSessionResponse(BaseModel):
    session: ChatSessionOut
    messages: list[ChatMessageOut]


class ChatMessageCreate(BaseModel):
    message: str


# --- Dashboard Schemas ---

class DocumentCounts(BaseModel):
    pending: int
    processing: int
    processed: int
    failed: int


class PipelineHealth(BaseModel):
    queue_depth: int
    avg_latency_ms: float


class DashboardSummaryResponse(BaseModel):
    documents: DocumentCounts
    entities_count: int
    active_agents: int
    recent_activity: list[dict]
    pipeline_health: PipelineHealth


# --- Agent Schemas ---

class AgentCreate(BaseModel):
    name: str
    type: str
    config: dict = {}


class AgentOut(BaseModel):
    id: str
    name: str
    type: str
    status: str
    created_at: datetime


class AgentTaskOut(BaseModel):
    id: str
    status: str
    input: dict | None
    output: dict | None
    trace: list[dict] | None
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None


class AgentListResponse(BaseModel):
    agents: list[AgentOut]


class AgentRunResponse(BaseModel):
    task_id: str
    status: str


# --- MCP Schemas ---

class MCPConnectionCreate(BaseModel):
    name: str
    direction: str
    endpoint_url: str | None = None
    auth_config: dict | None = None


class MCPConnectionOut(BaseModel):
    id: str
    name: str
    direction: str
    endpoint_url: str | None
    status: str


class MCPConnectionListResponse(BaseModel):
    connections: list[MCPConnectionOut]
