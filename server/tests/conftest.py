import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base
from app.models.student_profile import StudentProfile
from app.models.subject import Subject
from app.models.user import User

TEST_DB_URL = settings.DATABASE_URL


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession) -> dict:
    """Seed minimal test data: admin user, student user, student profile, subjects."""
    admin = User(
        phone="admin",
        nickname="Admin",
        role="admin",
        password_hash=hash_password("testpass"),
    )
    student_user = User(
        phone="13800000001",
        nickname="TestStudent",
        role="student",
        invite_token="test-student-token",
    )
    parent_user = User(
        phone="13800000002",
        nickname="TestParent",
        role="parent",
        invite_token="test-parent-token",
    )
    db_session.add_all([admin, student_user, parent_user])
    await db_session.flush()

    profile = StudentProfile(
        user_id=student_user.id,
        grade="高二",
        onboarding_completed=False,
    )
    db_session.add(profile)
    await db_session.flush()

    parent_user.linked_student_id = profile.id

    subjects = [
        Subject(name="语文", code="chinese", display_order=1),
        Subject(name="数学", code="math", display_order=2),
        Subject(name="英语", code="english", display_order=3),
        Subject(name="物理", code="physics", display_order=4),
        Subject(name="化学", code="chemistry", display_order=5),
    ]
    db_session.add_all(subjects)
    await db_session.flush()

    student_jwt = {
        "sub": str(student_user.id),
        "user_id": student_user.id,
        "role": "student",
        "student_id": profile.id,
    }
    student_token = create_access_token(student_jwt)
    admin_token = create_access_token(
        {"sub": str(admin.id), "user_id": admin.id, "role": "admin", "student_id": None}
    )
    parent_jwt = {
        "sub": str(parent_user.id),
        "user_id": parent_user.id,
        "role": "parent",
        "student_id": profile.id,
    }
    parent_token = create_access_token(parent_jwt)

    await db_session.commit()

    return {
        "admin": admin,
        "student_user": student_user,
        "parent_user": parent_user,
        "profile": profile,
        "subjects": subjects,
        "student_token": student_token,
        "admin_token": admin_token,
        "parent_token": parent_token,
    }
