from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeTree(Base):
    __tablename__ = "knowledge_tree"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("knowledge_tree.id"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text)
    textbook_versions: Mapped[dict | None] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    importance_score: Mapped[float | None] = mapped_column(Numeric(5, 4), default=0.5)
    exam_frequency: Mapped[int | None] = mapped_column(Integer, default=0)
    last_exam_year: Mapped[int | None] = mapped_column(Integer)
    syllabus_level: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StudentKnowledgeStatus(Base):
    __tablename__ = "student_knowledge_status"
    __table_args__ = (
        UniqueConstraint("student_id", "knowledge_point_id"),
        Index("idx_student_knowledge_student", "student_id"),
        Index("idx_student_knowledge_status", "status"),
        Index(
            "idx_student_knowledge_compound",
            "student_id",
            "status",
            "knowledge_point_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_tree.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="未观察")
    last_update_reason: Mapped[str | None] = mapped_column(String(100))
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_manual_corrected: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeUpdateLog(Base):
    __tablename__ = "knowledge_update_logs"
    __table_args__ = (
        Index("idx_knowledge_logs_student", "student_id", "created_at", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("knowledge_tree.id"), nullable=False
    )
    previous_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
