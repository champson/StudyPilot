import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.deps import get_redis
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import set_redis_client_for_testing
from app.core.security import create_access_token, hash_password
from app.llm import reset_model_router
from app.main import app
from app.models import Base
from app.models.knowledge import KnowledgeTree
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
    class FakeRedis:
        def __init__(self):
            self._data = {}

        async def get(self, key):
            return self._data.get(key)

        async def set(self, key, value):
            self._data[key] = value

        async def ping(self):
            return True

    fake_redis = FakeRedis()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # Use a nested transaction (SAVEPOINT) so that rollback undoes everything
        # including commits made by the application code via get_db override.
        async with session.begin():
            nested = await session.begin_nested()

            # Override get_db to reuse this session and re-open savepoints after commits
            async def override_get_db():
                nonlocal nested
                try:
                    yield session
                    # Application code calls commit() via get_db; absorb it as a
                    # nested savepoint commit so the outer txn stays open.
                    if nested.is_active:
                        await nested.commit()
                    nested = await session.begin_nested()
                except Exception:
                    if nested.is_active:
                        await nested.rollback()
                    nested = await session.begin_nested()
                    raise

            async def override_get_redis():
                yield fake_redis

            app.dependency_overrides[get_db] = override_get_db
            app.dependency_overrides[get_redis] = override_get_redis
            set_redis_client_for_testing(fake_redis)
            reset_model_router()
            yield session
            # Rollback the outer transaction — undoes ALL data written during the test
            await session.rollback()
        app.dependency_overrides.clear()
        set_redis_client_for_testing(None)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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
        subject_combination=["chinese", "math", "english", "physics", "chemistry"],
        onboarding_completed=True,
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

    math_root = KnowledgeTree(
        subject_id=subjects[1].id,
        name="函数基础",
        code="math-root",
        level=1,
    )
    physics_root = KnowledgeTree(
        subject_id=subjects[3].id,
        name="力学基础",
        code="physics-root",
        level=1,
    )
    english_root = KnowledgeTree(
        subject_id=subjects[2].id,
        name="词汇与语法",
        code="english-root",
        level=1,
    )
    db_session.add_all([math_root, physics_root, english_root])
    await db_session.flush()

    knowledge_points = [
        KnowledgeTree(
            subject_id=subjects[1].id,
            parent_id=math_root.id,
            name="函数的定义域",
            code="math-domain",
            level=2,
        ),
        KnowledgeTree(
            subject_id=subjects[1].id,
            parent_id=math_root.id,
            name="导数定义",
            code="math-derivative",
            level=2,
        ),
        KnowledgeTree(
            subject_id=subjects[3].id,
            parent_id=physics_root.id,
            name="牛顿第二定律",
            code="physics-newton-2",
            level=2,
        ),
        KnowledgeTree(
            subject_id=subjects[2].id,
            parent_id=english_root.id,
            name="Unit 5 词汇",
            code="english-unit-5-vocab",
            level=2,
        ),
    ]
    db_session.add_all(knowledge_points)
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

    return {
        "admin": admin,
        "student_user": student_user,
        "parent_user": parent_user,
        "profile": profile,
        "subjects": subjects,
        "knowledge_points": knowledge_points,
        "student_token": student_token,
        "admin_token": admin_token,
        "parent_token": parent_token,
    }
