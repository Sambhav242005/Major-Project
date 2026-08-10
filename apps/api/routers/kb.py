from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.security import get_current_user, User
from core.errors import NotFoundError
from core.security_utils import sanitize_input
from db.session import get_db
from services import knowledge as kb_service

router = APIRouter()


@router.get("/search")
async def search_knowledge_base(
    q: str = Query(..., min_length=1),
    top_k: int = Query(8, ge=1, le=20),
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    safe_q = sanitize_input(q)
    results = await kb_service.search(db, query=safe_q, project_id=project_id, top_k=top_k)
    return {"results": results, "query": safe_q}


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entity = await kb_service.get_entity(db, entity_id, project_id)
    if not entity:
        raise NotFoundError("Entity not found")
    return {"entity": entity}


@router.get("/entities/{entity_id}/chunks")
async def get_entity_chunks(
    entity_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chunks = await kb_service.get_entity_chunks(db, entity_id, project_id)
    return {"chunks": chunks}


@router.get("/graph")
async def get_graph(
    entity_id: str = Query(None),
    depth: int = Query(1, ge=1, le=3),
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    graph = await kb_service.get_graph(db, entity_id, project_id, depth)
    return graph
