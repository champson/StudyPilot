from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin


class StudyUpload(SoftDeleteMixin, Base):
    __tablename__ = "study_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    upload_type: Mapped[str] = mapped_column(String(30), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    original_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    ocr_result: Mapped[dict | None] = mapped_column(JSONB)
    extracted_questions: Mapped[dict | None] = mapped_column(JSONB, server_default="'[]'")
    subject_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("subjects.id"))
    knowledge_points: Mapped[dict | None] = mapped_column(JSONB, server_default="'[]'")
    ocr_status: Mapped[str] = mapped_column(String(20), default="pending")
    ocr_error: Mapped[str | None] = mapped_column(Text)
    is_manual_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
