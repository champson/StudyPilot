from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SubjectRiskState(Base):
    __tablename__ = "subject_risk_states"
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "effective_week"),
        Index("idx_risk_states_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="稳定")
    effective_week: Mapped[str] = mapped_column(String(10), nullable=False)
    calculation_detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    __table_args__ = (
        UniqueConstraint("student_id", "report_week"),
        Index("idx_weekly_reports_student_week", "student_id", "report_week", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    report_week: Mapped[str] = mapped_column(String(10), nullable=False)
    usage_days: Mapped[int | None] = mapped_column(Integer)
    total_minutes: Mapped[int | None] = mapped_column(Integer)
    student_view_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parent_view_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    share_summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    share_token: Mapped[str | None] = mapped_column(Text, unique=True)
    share_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
