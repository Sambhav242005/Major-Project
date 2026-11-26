from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models import Entity, Relationship
from db.session import Base
from services.chat.prompt import build_entity_context
from services.chat.retrieval import (
    _expand_via_graph,
    find_question_entities,
    select_graph_evidence,
    sources_with_project_header,
)


@pytest.mark.asyncio
async def test_graph_expansion_respects_depth_and_project():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    project_id, other_project = uuid4(), uuid4()
    vendor, contract, team, director, unrelated = [uuid4() for _ in range(5)]
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine)() as db:
            db.add_all([
                Entity(id=vendor, project_id=project_id, name="Atlas Vendor", type="org"),
                Entity(id=contract, project_id=project_id, name="Atlas Contract", type="concept"),
                Entity(id=team, project_id=project_id, name="Procurement Team", type="org"),
                Entity(id=director, project_id=project_id, name="Finance Director", type="person"),
                Entity(id=unrelated, project_id=other_project, name="Other Project", type="org"),
            ])
            await db.flush()
            db.add_all([
                Relationship(project_id=project_id, source_entity_id=source,
                             target_entity_id=target, relation_type=relation)
                for source, target, relation in [
                    (vendor, contract, "supplies_under"),
                    (team, contract, "owns"),
                    (team, director, "reports_to"),
                    (contract, vendor, "references"),
                    (contract, unrelated, "mentions"),
                ]
            ])
            await db.commit()
        async with async_sessionmaker(engine)() as db:
            seeds = await find_question_entities(
                db, str(project_id), "Who owns ATLAS VENDOR's contract? Other Project has a copy."
            )
            assert [seed["id"] for seed in seeds] == [str(vendor)]
            expected = ["Atlas Contract", "Procurement Team", "Finance Director"]
            for depth in (0, 1, 2, 3, 8):
                entities = await _expand_via_graph(db, str(project_id), [str(vendor)], depth)
                assert [entity["name"] for entity in entities] == expected[:depth]
                prompt = build_entity_context([], entities)
                assert ("Procurement Team" in prompt) == (depth >= 2)
    finally:
        await engine.dispose()


def test_governance_passage_only_replaces_an_off_topic_vector_hit():
    approved = {"visible_text": "Project: Atlas\nApproved value is 60."}
    draft = {"visible_text": "Project: Atlas\nDraft value is 120."}
    unrelated = {"visible_text": "Project: Cedar\nUnrelated text."}
    rule = {"visible_text": "Project: Atlas\nGovernance rule: Drafts do not replace approved records."}
    wrong_rule = {"visible_text": "Project: Cedar\nGovernance rule: Drafts are valid."}
    assert sources_with_project_header([wrong_rule, rule], [{"name": "ATLAS"}]) == [rule]
    assert select_graph_evidence("What is the value for Atlas?", [approved, unrelated, draft],
                                 [wrong_rule, rule]) == [approved, rule, draft]
    assert select_graph_evidence("What is the value for Atlas?", [approved, draft], [rule]) == [approved, draft]
