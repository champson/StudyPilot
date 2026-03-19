from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeTree, StudentKnowledgeStatus


async def get_knowledge_status(
    db: AsyncSession, student_id: int, subject_id: int | None = None
) -> list[dict]:
    query = (
        select(StudentKnowledgeStatus, KnowledgeTree.name, KnowledgeTree.subject_id)
        .join(
            KnowledgeTree,
            StudentKnowledgeStatus.knowledge_point_id == KnowledgeTree.id,
        )
        .where(StudentKnowledgeStatus.student_id == student_id)
    )
    if subject_id is not None:
        query = query.where(KnowledgeTree.subject_id == subject_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": row[0].id,
            "student_id": row[0].student_id,
            "knowledge_point_id": row[0].knowledge_point_id,
            "status": row[0].status,
            "last_update_reason": row[0].last_update_reason,
            "last_updated_at": row[0].last_updated_at,
            "is_manual_corrected": row[0].is_manual_corrected,
            "point_name": row[1],
            "subject_id": row[2],
        }
        for row in rows
    ]
