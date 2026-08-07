"""Knowledge base service — semantic search, entity lookup, graph traversal."""

import logging
from collections import defaultdict

import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Entity, EntityMention, Relationship, DocumentChunk, Document
from pipelines.embeddings import query_chunks

logger = logging.getLogger(__name__)


async def search(
    db: AsyncSession,
    query: str,
    project_id: str,
    top_k: int = 8,
) -> list[dict]:
    """Semantic search over project's ingested chunks.

    Returns list of dicts with chunk_id, text, score, document info.
    """
    # Step 1: ChromaDB similarity search
    chroma_results = query_chunks(query=query, project_id=project_id, top_k=top_k)

    if not chroma_results:
        return []

    # Step 2: Enrich with document metadata from Postgres
    results = []
    for r in chroma_results:
        # Get chunk metadata from Postgres
        stmt = select(DocumentChunk).where(DocumentChunk.chroma_id == r["chunk_id"])
        db_result = await db.execute(stmt)
        chunk = db_result.scalar_one_or_none()

        if chunk:
            # Get document info
            doc_stmt = select(Document).where(Document.id == chunk.document_id)
            doc_result = await db.execute(doc_stmt)
            doc = doc_result.scalar_one_or_none()

            results.append({
                "chunk_id": r["chunk_id"],
                "document_id": r.get("document_id", str(chunk.document_id)),
                "text": r["text"],
                "score": r["score"],
                "page_number": r.get("page_number", chunk.page_number),
                "filename": doc.filename if doc else "unknown",
                "chunk_index": chunk.chunk_index,
            })
        else:
            results.append({
                "chunk_id": r["chunk_id"],
                "document_id": r.get("document_id", ""),
                "text": r["text"],
                "score": r["score"],
                "page_number": r.get("page_number", 0),
                "filename": "unknown",
                "chunk_index": 0,
            })

    return results


async def get_entity(db: AsyncSession, entity_id: str, project_id: str) -> dict | None:
    """Fetch entity with its mentions and relationships."""
    stmt = select(Entity).where(
        Entity.id == entity_id,
        Entity.project_id == project_id,
    )
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()

    if not entity:
        return None

    # Get mentions
    mention_stmt = select(EntityMention).where(EntityMention.entity_id == entity.id)
    mention_result = await db.execute(mention_stmt)
    mentions = mention_result.scalars().all()

    # Get relationships
    rel_stmt = select(Relationship).where(
        (Relationship.source_entity_id == entity.id)
        | (Relationship.target_entity_id == entity.id)
    )
    rel_result = await db.execute(rel_stmt)
    relationships = rel_result.scalars().all()

    # Format relationships
    rel_list = []
    for rel in relationships:
        other_id = (
            rel.target_entity_id if rel.source_entity_id == entity.id
            else rel.source_entity_id
        )
        # Get other entity name
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
    """Get entity graph as nodes and edges.

    If entity_id is provided, returns subgraph around that entity.
    Otherwise returns the full project graph.
    """
    # Load all entities in project
    entity_stmt = select(Entity).where(Entity.project_id == project_id)
    entity_result = await db.execute(entity_stmt)
    entities = entity_result.scalars().all()

    # Load all relationships in project
    rel_stmt = select(Relationship).where(Relationship.project_id == project_id)
    rel_result = await db.execute(rel_stmt)
    relationships = rel_result.scalars().all()

    # Build NetworkX graph
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

    # If entity_id specified, extract subgraph around it
    if entity_id and entity_id in G:
        nodes_of_interest = {entity_id}
        current_layer = {entity_id}

        for _ in range(depth):
            next_layer = set()
            for node in current_layer:
                # Add neighbors (both directions)
                next_layer.update(G.predecessors(node))
                next_layer.update(G.successors(node))
            nodes_of_interest.update(next_layer)
            current_layer = next_layer

        subgraph = G.subgraph(nodes_of_interest)
    else:
        subgraph = G

    # Format output
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
    # Get all mentions for this entity
    stmt = select(EntityMention).where(EntityMention.entity_id == entity_id)
    result = await db.execute(stmt)
    mentions = result.scalars().all()

    chunks = []
    for mention in mentions:
        chunk_stmt = select(DocumentChunk).where(DocumentChunk.id == mention.chunk_id)
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
