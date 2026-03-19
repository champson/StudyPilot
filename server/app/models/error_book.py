from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin


class ErrorBook(SoftDeleteMixin, Base):
    __tablename__ = "error_book"
    __table_args__ = (
        Index(
            "idx_error_book_dedup",
            "student_id",
            "content_hash",
            unique=True,
            postgresql_where=text("content_hash IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    question_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    question_image_url: Mapped[str | None] = mapped_column(String(500))
    knowledge_points: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="'[]'")
    error_type: Mapped[str | None] = mapped_column(String(50))
    entry_reason: Mapped[str] = mapped_column(String(50), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    is_explained: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recalled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_recall_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_recall_result: Mapped[str | None] = mapped_column(String(20))
    recall_count: Mapped[int] = mapped_column(Integer, default=0)
    source_upload_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("study_uploads.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
