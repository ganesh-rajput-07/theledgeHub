import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class ExtractionStatus:
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    FAILED = "failed"


class Extraction(Base):
    """Structured values read from one document according to a DocumentSchema, awaiting or past human review."""

    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    schema_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default=ExtractionStatus.PROCESSING, nullable=False)
    values: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    issues: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    # Normalized identity of the document (e.g. vendor GSTIN + invoice number), for duplicate detection.
    duplicate_key: Mapped[str | None] = mapped_column(Text, index=True)
    model: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # One-way: deleting a document removes its extraction in the database (ON DELETE CASCADE).
    document = relationship("Document")

    @property
    def filename(self) -> str:
        return self.document.filename


class ExtractionRuleSet(Base):
    """A workspace's validation rules for one document type: predefined rules switched on/off and tuned, plus
    custom rules. Stored as validated JSON (app.extraction.rules.RuleConfig); no row means the defaults."""

    __tablename__ = "extraction_rule_sets"
    __table_args__ = (UniqueConstraint("workspace_id", "schema_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schema_key: Mapped[str] = mapped_column(String(60), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
