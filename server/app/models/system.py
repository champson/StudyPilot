from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ModelCallLog(Base):
    __tablename__ = "model_call_logs"
    __table_args__ = (
        Index("idx_model_logs_created", "created_at", postgresql_using="btree"),
        Index("idx_model_logs_agent", "agent_name", "created_at", postgresql_using="btree"),
        Index("idx_model_logs_student", "student_id", "created_at", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    student_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("student_profiles.id")
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(10, 6))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ManualCorrection(Base):
    __tablename__ = "manual_corrections"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('ocr', 'knowledge', 'plan', 'qa')",
            name="chk_target_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'resolved', 'rejected')",
            name="chk_correction_status",
        ),
        Index("idx_corrections_type", "target_type", "created_at", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    original_content: Mapped[dict | None] = mapped_column(JSONB)
    corrected_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    correction_reason: Mapped[str | None] = mapped_column(Text)
    corrected_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
