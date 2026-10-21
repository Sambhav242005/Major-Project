"""Local credentials, separate from domain profiles and Supabase identities."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


class LocalAccount(Base):
    __tablename__ = "local_accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
