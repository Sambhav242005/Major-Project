"""Knowledge graph — entity lookup, graph traversal, entity chunks."""

import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document, DocumentChunk, Entity, EntityMention, Relationship

from .search import _uuid_val


async def get_entity(db: AsyncSession, entity_id: str, project_id: str) -> dict | None:
    """Fetch entity with its mentions and relationships."""
    stmt = select(Entity).where(
        Entity.id == _uuid_val(entity_id),
        Entity.project_id == _uuid_val(project_id),
    )
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()

    if not entity:
        return None

    mention_stmt = select(EntityMention).where(EntityMention.entity_id == entity.id)
    mention_result = await db.execute(mention_stmt)
    mentions = mention_result.scalars().all()

    rel_stmt = select(Relationship).where(
        (Relationship.source_entity_id == entity.id)
        | (Relationship.target_entity_id == entity.id)
    )
    rel_result = await db.execute(rel_stmt)
    relationships = rel_result.scalars().all()

    rel_list = []
    for rel in relationships:
        other_id = (
            rel.target_entity_id if rel.source_entity_id == entity.id
            else rel.source_entity_id
        )
        other_stmt = select(Entity).where(Entity.id == other_id)
        other_result = await db.execute(other_stmt)
        other = other_result.scalar_one_or_none()

        rel_list.append({
            "id": str(rel.id),
            "relation_type": rel.relation_type,
            "description": rel.description,
            "confidence": rel.confidence,
            "other_entity_id": str(other_id),
            "other_entity_name": other.name if other else "unknown",
            "direction": "outgoing" if rel.source_entity_id == entity.id else "incoming",
        })

    return {
        "id": str(entity.id),
        "name": entity.name,
        "type": entity.type,
        "description": entity.description,
        "first_seen_document_id": str(entity.first_seen_document_id) if entity.first_seen_document_id else None,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "mentions_count": len(mentions),
        "relationships": rel_list,
    }


async def get_graph(
    db: AsyncSession,
    entity_id: str | None,
    project_id: str,
    depth: int = 1,
) -> dict:
    """Get entity graph as nodes and edges."""
    entity_stmt = select(Entity).where(Entity.project_id == _uuid_val(project_id))
    entity_result = await db.execute(entity_stmt)
    entities = entity_result.scalars().all()

    rel_stmt = select(Relationship).where(Relationship.project_id == _uuid_val(project_id))
    rel_result = await db.execute(rel_stmt)
    relationships = rel_result.scalars().all()

    G = nx.DiGraph()

    for e in entities:
        G.add_node(
            str(e.id),
            name=e.name,
            type=e.type,
            description=e.description or "",
        )

    for rel in relationships:
        src = str(rel.source_entity_id)
        tgt = str(rel.target_entity_id)
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(
                src,
                tgt,
                relation_type=rel.relation_type,
                description=rel.description or "",
                confidence=rel.confidence or 0.0,
                id=str(rel.id),
            )

    if entity_id and entity_id in G:
        nodes_of_interest = {entity_id}
        current_layer = {entity_id}

        for _ in range(depth):
            next_layer = set()
            for node in current_layer:
                next_layer.update(G.predecessors(node))
                next_layer.update(G.successors(node))
            nodes_of_interest.update(next_layer)
            current_layer = next_layer

        subgraph = G.subgraph(nodes_of_interest)
    else:
        subgraph = G

    nodes = []
    for node_id, data in subgraph.nodes(data=True):
        nodes.append({
            "id": node_id,
            "name": data.get("name", ""),
            "type": data.get("type", ""),
            "description": data.get("description", ""),
        })

    edges = []
    for src, tgt, data in subgraph.edges(data=True):
        edges.append({
            "id": data.get("id", ""),
            "source": src,
            "target": tgt,
            "relation_type": data.get("relation_type", ""),
            "description": data.get("description", ""),
            "confidence": data.get("confidence", 0.0),
        })

    return {"nodes": nodes, "edges": edges}


async def get_entity_chunks(
    db: AsyncSession,
    entity_id: str,
    project_id: str,
) -> list[dict]:
    """Get chunks that mention a specific entity."""
    stmt = select(EntityMention).where(EntityMention.entity_id == _uuid_val(entity_id))
    result = await db.execute(stmt)
    mentions = result.scalars().all()

    chunks = []
    for mention in mentions:
        chunk_stmt = select(DocumentChunk).where(DocumentChunk.id == _uuid_val(mention.chunk_id))
        chunk_result = await db.execute(chunk_stmt)
        chunk = chunk_result.scalar_one_or_none()

        if chunk:
            doc_stmt = select(Document).where(Document.id == chunk.document_id)
            doc_result = await db.execute(doc_stmt)
            doc = doc_result.scalar_one_or_none()

            chunks.append({
                "chunk_id": str(chunk.id),
                "text": chunk.text,
                "page_number": chunk.page_number,
                "filename": doc.filename if doc else "unknown",
                "mention_text": mention.mention_text,
                "confidence": mention.confidence,
            })

    return chunks
