from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class QaSession(Base):
    __tablename__ = "qa_sessions"
    __table_args__ = (
        Index("idx_qa_sessions_student", "student_id", "created_at", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("student_profiles.id"), nullable=False
    )
    session_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today,
        server_default=func.current_date(),
    )
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("plan_tasks.id"))
    subject_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("subjects.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    structured_summary: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    messages: Mapped[list["QaMessage"]] = relationship(back_populates="session")


class QaMessage(Base):
    __tablename__ = "qa_messages"
    __table_args__ = (
        Index("idx_qa_messages_session", "session_id", "created_at", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("qa_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    intent: Mapped[str | None] = mapped_column(String(50))
    related_question_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("error_book.id"))
    knowledge_points: Mapped[dict | None] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    tutoring_strategy: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["QaSession"] = relationship(back_populates="messages")
