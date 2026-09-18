from pydantic import BaseModel


class EntityOut(BaseModel):
    id: str
    name: str
    type: str
    description: str | None
    first_seen_document_id: str | None


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


class EntityDetailResponse(BaseModel):
    entity: EntityOut
    relationships: list[RelationshipOut]
    mentions: list[EntityMentionOut]
