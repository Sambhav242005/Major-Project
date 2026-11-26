"""Chat retrieval — entity context, graph expansion, source formatting."""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import DocumentChunk, Entity, EntityMention

# Per-source block characters included in the prompt by _format_source_block.
SOURCE_TEXT_TRUNCATE_CHARS = 800


async def find_question_entities(db: AsyncSession, project_id: str, question: str) -> list[dict]:
    """Find project entities named explicitly in a question for KG-first evaluation."""
    entities = await db.scalars(
        select(Entity).where(Entity.project_id == uuid.UUID(project_id)).order_by(Entity.id)
    )
    return [
        {"id": str(entity.id), "name": entity.name, "type": entity.type,
         "description": entity.description}
        for entity in entities
        if re.search(r"(?<!\w)" + re.escape(entity.name) + r"(?!\w)", question, re.IGNORECASE)
    ]


def sources_with_project_header(sources: list[dict], entities: list[dict]) -> list[dict]:
    """Recover explicit project references that entity extraction omitted."""
    names = {entity["name"].casefold() for entity in entities}
    return [source for source in sources if _project_header(source) in names]


def _project_header(source: dict) -> str | None:
    match = re.search(r"^Project:[ \t]*(.+)$", source["visible_text"], re.MULTILINE)
    return match[1].strip().casefold() if match else None


def select_graph_evidence(
    question: str, vector_sources: list[dict], graph_sources: list[dict],
) -> list[dict]:
    """Supplement vector results with an applicable governance passage when missing."""
    if not vector_sources:
        return vector_sources

    def has_rule(source: dict) -> bool:
        return bool(re.search(r"^Governance rule:", source["visible_text"], re.IGNORECASE | re.MULTILINE))

    subjects = {
        name for source in vector_sources + graph_sources
        if (name := _project_header(source)) and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", question, re.IGNORECASE)
    }
    if len(subjects) != 1:
        return vector_sources
    target = subjects.pop()
    if any(_project_header(source) == target and has_rule(source) for source in vector_sources):
        return vector_sources
    rule = next((source for source in graph_sources if _project_header(source) == target and has_rule(source)), None)
    if rule is None:
        return vector_sources

    # Preserve all passages explicitly about the requested project and keep
    # the strongest hit. Only replace a lower-ranked, explicitly off-topic hit.
    for index in range(len(vector_sources) - 1, 0, -1):
        if (name := _project_header(vector_sources[index])) and name != target:
            return [*vector_sources[:index], rule, *vector_sources[index + 1:]]
    return vector_sources


async def _get_entity_context(
    db: AsyncSession,
    project_id: str,
    chunk_ids: list[str],
) -> list[dict]:
    """Get entities mentioned in retrieved chunks for graph expansion.

    chunk_ids are Chroma IDs (e.g. "{document_id}_chunk_{n}") from
    query_chunks — map them to real DB chunk UUIDs before querying mentions,
    otherwise uuid.UUID() explodes on the compound id.
    """
    chroma_ids = [cid for cid in chunk_ids if cid]
    if not chroma_ids:
        return []

    # Map Chroma IDs -> DB chunk UUIDs
    chunk_stmt = select(DocumentChunk.id).where(DocumentChunk.chroma_id.in_(chroma_ids))
    chunk_result = await db.execute(chunk_stmt)
    db_chunk_ids = [row[0] for row in chunk_result.all()]

    if not db_chunk_ids:
        return []

    # Find entities that appear in these chunks
    stmt = select(EntityMention).where(EntityMention.chunk_id.in_(db_chunk_ids))
    result = await db.execute(stmt)
    mentions = result.scalars().all()

    entity_ids = list(set(m.entity_id for m in mentions))

    if not entity_ids:
        return []

    # Get entity details
    ent_stmt = select(Entity).where(Entity.id.in_(entity_ids))
    ent_result = await db.execute(ent_stmt)
    entities = ent_result.scalars().all()

    return [
        {
            "id": str(e.id),
            "name": e.name,
            "type": e.type,
            "description": e.description,
        }
        for e in entities
    ]


async def _expand_via_graph(
    db: AsyncSession,
    project_id: str,
    entity_ids: list[str],
    depth: int = 1,
) -> list[dict]:
    """Return project-local neighbors in order of increasing hop distance."""
    from db.models import Relationship

    if not entity_ids or depth <= 0:
        return []

    project_uuid = uuid.UUID(project_id)
    frontier = {uuid.UUID(entity_id) for entity_id in entity_ids if entity_id}
    visited = set(frontier)
    neighbors = []
    for _ in range(depth):
        if not frontier:
            break
        edges = await db.execute(
            select(Relationship.source_entity_id, Relationship.target_entity_id).where(
                Relationship.project_id == project_uuid,
                (Relationship.source_entity_id.in_(frontier))
                | (Relationship.target_entity_id.in_(frontier)),
            )
        )
        neighbor_ids = {endpoint for edge in edges for endpoint in edge} - visited - {None}
        if not neighbor_ids:
            break
        visited.update(neighbor_ids)
        result = await db.scalars(
            select(Entity)
            .where(Entity.project_id == project_uuid, Entity.id.in_(neighbor_ids))
            .order_by(Entity.id)
        )
        hop_neighbors = result.all()
        neighbors.extend(hop_neighbors)
        frontier = {entity.id for entity in hop_neighbors}
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "type": e.type,
            "description": e.description,
        }
        for e in neighbors
    ]


def _format_source_block(
    index: int,
    text: str,
    filename: str,
    page_number: int,
    doc_id: str,
    source_location: dict | None = None,
) -> str:
    """Format a source block for the LLM prompt."""
    header = f"[Source {index}] Document: {filename}, Page: {page_number or 'N/A'}"
    if source_location:
        header = (f"[Source {index}] Document: {filename}, "
                  f"Time: {source_location['start_seconds']:.2f}-{source_location['end_seconds']:.2f}s, "
                  f"Evidence: {source_location['kind']} (machine generated)")
    return f"{header}\n{text[:SOURCE_TEXT_TRUNCATE_CHARS]}"  # Truncate long chunks
