from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, desc, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class StudentProfile(TimestampMixin, Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False
    )
    grade: Mapped[str] = mapped_column(String(20), nullable=False)
    textbook_version: Mapped[str | None] = mapped_column(String(50))
    class_rank: Mapped[int | None] = mapped_column(Integer)
    grade_rank: Mapped[int | None] = mapped_column(Integer)
    subject_combination: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="'[]'")
    upcoming_exams: Mapped[dict | None] = mapped_column(JSONB, server_default="'[]'")
    current_progress: Mapped[dict | None] = mapped_column(JSONB, server_default="'{}'")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    onboarding_data: Mapped[dict | None] = mapped_column(JSONB, server_default="'{}'")

    user: Mapped["User"] = relationship(
        "User",
        back_populates="student_profile",
        foreign_keys=[user_id],
    )
    exam_records: Mapped[list["ExamRecord"]] = relationship(back_populates="student")


class ExamRecord(Base):
    __tablename__ = "exam_records"
    __table_args__ = (
        Index("idx_exam_records_student_date", "student_id", desc("exam_date")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    exam_type: Mapped[str] = mapped_column(String(50), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    full_score: Mapped[float | None] = mapped_column(Numeric(5, 2), default=100)
    class_rank: Mapped[int | None] = mapped_column(Integer)
    grade_rank: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(20), default="student")

    student: Mapped["StudentProfile"] = relationship(back_populates="exam_records")
