from pydantic import BaseModel


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
