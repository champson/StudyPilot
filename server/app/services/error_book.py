from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.error_book import ErrorBook
from app.models.subject import Subject


async def list_errors(
    db: AsyncSession,
    student_id: int,
    page: int,
    page_size: int,
    subject_id: int | None = None,
    is_recalled: bool | None = None,
) -> tuple[list[ErrorBook], int]:
    conditions = [
        ErrorBook.student_id == student_id,
        ErrorBook.is_deleted == False,  # noqa: E712
    ]
    if subject_id is not None:
        conditions.append(ErrorBook.subject_id == subject_id)
    if is_recalled is not None:
        conditions.append(ErrorBook.is_recalled == is_recalled)

    count_result = await db.execute(
        select(func.count(ErrorBook.id)).where(*conditions)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ErrorBook)
        .where(*conditions)
        .order_by(ErrorBook.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return result.scalars().all(), total


async def get_error_summary(db: AsyncSession, student_id: int) -> dict:
    base_cond = [
        ErrorBook.student_id == student_id,
        ErrorBook.is_deleted == False,  # noqa: E712
    ]
    total_result = await db.execute(
        select(func.count(ErrorBook.id)).where(*base_cond)
    )
    total = total_result.scalar() or 0

    recalled_result = await db.execute(
        select(func.count(ErrorBook.id)).where(
            *base_cond, ErrorBook.is_recalled == True  # noqa: E712
        )
    )
    recalled = recalled_result.scalar() or 0
    unrecalled = total - recalled

    # Per-subject breakdown with unrecalled count and subject name
    by_subject_result = await db.execute(
        select(
            ErrorBook.subject_id,
            func.count(ErrorBook.id),
            func.count(ErrorBook.id).filter(
                ErrorBook.is_recalled == False  # noqa: E712
            ),
        )
        .where(*base_cond)
        .group_by(ErrorBook.subject_id)
    )
    by_subject_rows = by_subject_result.all()

    # Look up subject names
    subject_ids = [row[0] for row in by_subject_rows]
    subject_name_map: dict[int, str] = {}
    if subject_ids:
        subj_result = await db.execute(
            select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
        )
        subject_name_map = {r[0]: r[1] for r in subj_result.all()}

    by_subject = [
        {
            "subject_id": row[0],
            "subject_name": subject_name_map.get(row[0], ""),
            "count": row[1],
            "unrecalled": row[2],
        }
        for row in by_subject_rows
    ]

    # Per error_type breakdown
    by_type_result = await db.execute(
        select(ErrorBook.error_type, func.count(ErrorBook.id))
        .where(*base_cond)
        .group_by(ErrorBook.error_type)
    )
    by_error_type = {
        (row[0] or "unknown"): row[1] for row in by_type_result.all()
    }

    return {
        "total": total,
        "unrecalled": unrecalled,
        "by_subject": by_subject,
        "by_error_type": by_error_type,
    }


async def get_error_detail(
    db: AsyncSession, student_id: int, error_id: int
) -> ErrorBook:
    result = await db.execute(
        select(ErrorBook).where(
            ErrorBook.id == error_id,
            ErrorBook.student_id == student_id,
            ErrorBook.is_deleted == False,  # noqa: E712
        )
    )
    error = result.scalar_one_or_none()
    if not error:
        raise AppError("ERROR_NOT_FOUND", "错题不存在", status_code=404)
    return error


async def recall_error(
    db: AsyncSession, student_id: int, error_id: int, result_str: str
) -> ErrorBook:
    error = await get_error_detail(db, student_id, error_id)
    now = datetime.now(UTC)
    error.is_recalled = True
    error.last_recall_at = now
    error.last_recall_result = result_str
    error.recall_count += 1
    await db.flush()
    return error


async def batch_recall(
    db: AsyncSession, student_id: int, items: list
) -> list[ErrorBook]:
    results = []
    for item in items:
        error = await recall_error(db, student_id, item.id, item.result)
        results.append(error)
    return results
