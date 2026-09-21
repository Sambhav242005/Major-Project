import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship

from db.session import Base


def gen_uuid():
    return uuid.uuid4()


__all__ = [
    "Base",
    "Boolean",
    "Column",
    "DateTime",
    "Float",
    "ForeignKey",
    "Integer",
    "JSON",
    "String",
    "Text",
    "UniqueConstraint",
    "Uuid",
    "datetime",
    "gen_uuid",
    "relationship",
]
