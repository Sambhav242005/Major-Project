"""Fresh database identities must match auth subjects and every owner FK."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.deps import _NS, _user_uuid, get_project_id
from core.security import User
from db.models import Agent, ChatSession, Document, Profile, Project, ProjectMember
from db.session import Base
from services.agents.crud import create_agent
from services.chat.sessions import create_session
from services.documents.crud import upload_document


def test_user_uuid_preserves_auth_identity_and_mock_fallback():
    subject = "550E8400-E29B-41D4-A716-446655440000"
    assert _user_uuid(subject) == uuid.UUID(subject)
    assert _user_uuid("mock-user") == uuid.uuid5(_NS, "mock-user")


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", ["550e8400-e29b-41d4-a716-446655440000", "mock-user"])
@pytest.mark.parametrize("existing_profile", [False, True])
async def test_bootstrap_and_resource_owners_share_enforced_profile_fk(subject, existing_profile):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        user = User(id=subject, email="owner@example.com")
        expected_id = _user_uuid(subject)

        async with sessions() as db:
            assert await db.scalar(text("PRAGMA foreign_keys")) == 1
            # Supabase can provision the profile with its original auth UUID.
            # Bootstrap must reuse it rather than hash it into a second identity.
            if existing_profile:
                db.add(Profile(id=expected_id, full_name="Existing owner"))
                await db.commit()
            project_id = await get_project_id(user=user, db=db, project_id=None)
            document = await upload_document(
                db, user, "source.txt", "text/plain", "source.txt", project_id
            )
            agent = await create_agent(db, user, project_id, "Reader", "qa")
            chat = await create_session(db, user, project_id)
            await db.commit()

        async with sessions() as db:
            profiles = (await db.scalars(select(Profile))).all()
            assert [profile.id for profile in profiles] == [expected_id]
            assert profiles[0].full_name == ("Existing owner" if existing_profile else user.email)
            project_uuid = uuid.UUID(project_id)
            assert (await db.get(Project, project_uuid)).owner_id == expected_id
            assert await db.get(ProjectMember, (project_uuid, expected_id)) is not None
            assert (await db.get(Document, uuid.UUID(document["id"]))).uploaded_by == expected_id
            assert (await db.get(Agent, uuid.UUID(agent["id"]))).owner_id == expected_id
            assert (await db.get(ChatSession, uuid.UUID(chat["id"]))).user_id == expected_id
            assert await get_project_id(user=user, db=db, project_id=None) == project_id
            assert await get_project_id(user=user, db=db, project_id=project_id) == project_id
            with pytest.raises(HTTPException) as forbidden:
                await get_project_id(
                    user=User(id=str(uuid.uuid4())), db=db, project_id=project_id
                )
            assert forbidden.value.status_code == 403

            # Prove this database really rejects an orphaned resource owner.
            db.add(Document(
                project_id=project_uuid, uploaded_by=uuid.uuid4(), filename="orphan.txt",
                file_type="text/plain", storage_path="orphan.txt",
            ))
            with pytest.raises(IntegrityError):
                await db.flush()
            await db.rollback()
    finally:
        await engine.dispose()
