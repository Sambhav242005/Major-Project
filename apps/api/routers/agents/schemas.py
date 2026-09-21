"""Pydantic schemas for agents router."""

from pydantic import BaseModel


class AgentCreateRequest(BaseModel):
    name: str
    type: str
    config: dict = {}


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    config: dict | None = None
    status: str | None = None


class AgentRunRequest(BaseModel):
    input: dict = {}


class MemoryStoreRequest(BaseModel):
    memory_type: str  # working, episodic, semantic
    content: dict
    embedding: list[float] | None = None
    metadata: dict = {}
    ttl_hours: int | None = None


class CheckpointSaveRequest(BaseModel):
    state: dict
    task_id: str | None = None
