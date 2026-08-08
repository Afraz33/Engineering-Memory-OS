import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

try:
    from pgvector.sqlalchemy import Vector  # type: ignore[import]
except ImportError:
    from sqlalchemy import LargeBinary as Vector  # type: ignore[assignment]


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[object] = mapped_column(Vector(768), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    namespace: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_embeddings_namespace", "namespace"),
        Index("ix_embeddings_model", "model"),
    )
