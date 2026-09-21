from datetime import datetime

from pydantic import BaseModel


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
