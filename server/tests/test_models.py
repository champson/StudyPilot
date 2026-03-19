import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subject import Subject
from app.models.user import User


@pytest.mark.asyncio
async def test_all_tables_created(engine):
    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    expected = {
        "users",
        "student_profiles",
        "exam_records",
        "subjects",
        "knowledge_tree",
        "student_knowledge_status",
        "knowledge_update_logs",
        "daily_plans",
        "plan_tasks",
        "study_uploads",
        "qa_sessions",
        "qa_messages",
        "error_book",
        "subject_risk_states",
        "weekly_reports",
        "model_call_logs",
        "manual_corrections",
    }
    missing = expected - set(table_names)
    assert not missing, f"Missing tables: {missing}"


@pytest.mark.asyncio
async def test_user_crud(db_session: AsyncSession):
    user = User(phone="test_crud_user", nickname="CrudTest", role="student")
    db_session.add(user)
    await db_session.flush()

    result = await db_session.execute(select(User).where(User.phone == "test_crud_user"))
    fetched = result.scalar_one()
    assert fetched.nickname == "CrudTest"
    assert fetched.id is not None


@pytest.mark.asyncio
async def test_subject_uniqueness(db_session: AsyncSession):
    s1 = Subject(name="TestSubject", code="test_subj", display_order=99)
    db_session.add(s1)
    await db_session.flush()

    s2 = Subject(name="TestSubject", code="test_subj_dup", display_order=100)
    db_session.add(s2)
    with pytest.raises(Exception):
        await db_session.flush()
