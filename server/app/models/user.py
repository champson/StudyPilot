from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    password_hash: Mapped[str | None] = mapped_column(String(200))
    invite_token: Mapped[str | None] = mapped_column(String(100), unique=True)
    linked_student_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("student_profiles.id")
    )

    student_profile: Mapped["StudentProfile | None"] = relationship(
        "StudentProfile",
        back_populates="user",
        foreign_keys="StudentProfile.user_id",
    )
