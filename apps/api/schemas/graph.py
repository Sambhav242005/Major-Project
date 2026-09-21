from pydantic import BaseModel


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
