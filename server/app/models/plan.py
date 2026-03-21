from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin


class DailyPlan(SoftDeleteMixin, Base):
    __tablename__ = "daily_plans"
    __table_args__ = (
        Index(
            "idx_daily_plan_unique_active",
            "student_id",
            "plan_date",
            unique=True,
            postgresql_where="is_deleted = false",
        ),
        Index("idx_daily_plans_student_date", "student_id", desc("plan_date")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    learning_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    system_recommended_mode: Mapped[str | None] = mapped_column(String(30))
    available_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    is_history_inferred: Mapped[bool] = mapped_column(Boolean, default=False)
    recommended_subjects: Mapped[dict] = mapped_column(JSONB, nullable=False)
    plan_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generated")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tasks: Mapped[list["PlanTask"]] = relationship(
        back_populates="plan", order_by="PlanTask.sequence"
    )


class PlanTask(Base):
    __tablename__ = "plan_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("daily_plans.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    task_content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)

    plan: Mapped["DailyPlan"] = relationship(back_populates="tasks")
