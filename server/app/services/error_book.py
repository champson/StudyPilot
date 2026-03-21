from datetime import UTC, datetime
from collections import defaultdict
import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.error_book import ErrorBook
from app.models.knowledge import KnowledgeTree, StudentKnowledgeStatus
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


# ---------------------------------------------------------------------------
# 错题召回优先级算法 - 参考 phase3-detailed-design.md §5.7
# ---------------------------------------------------------------------------

# 状态权重映射表
STATUS_WEIGHT_MAP = {
    "反复失误": 50,
    "需要巩固": 30,
    "初步接触": 20,
    "基本掌握": 0,
    "完全掌握": 0,
    "未观察": 10,
}

# 召回批次默认限制
DEFAULT_RECALL_BATCH_SIZE = 20
MAX_ERRORS_PER_KNOWLEDGE_POINT = 3
MAX_RECALL_COUNT_THRESHOLD = 3  # 已成功召回 ≥3 次的题目排除


def _calculate_priority_score(
    status_weight: int,
    days_since_error: float,
    importance_score: float,
    recall_count: int,
) -> float:
    """
    计算错题召回优先级分数
    
    公式: priority_score = status_weight + recency_weight + importance_weight - recall_penalty
    - status_weight: 知识点掌握状态权重 (0-50)
    - recency_weight: 30 × e^(-days_since_error / 14) (0-30)
    - importance_weight: 20 × importance_score (0-20)
    - recall_penalty: 10 × recall_count (已成功召回次数)
    """
    # 时间衰减权重: 14天半衰期
    recency_weight = 30 * math.exp(-days_since_error / 14)
    
    # 重要性权重
    importance_weight = 20 * importance_score
    
    # 召回惩罚
    recall_penalty = 10 * min(recall_count, 3)  # 最多扣 30 分
    
    return status_weight + recency_weight + importance_weight - recall_penalty


async def get_recall_batch(
    db: AsyncSession,
    student_id: int,
    batch_size: int = DEFAULT_RECALL_BATCH_SIZE,
    subject_id: int | None = None,
) -> list[ErrorBook]:
    """
    获取错题召回批次
    
    规则:
    1. 按优先级分数降序排列
    2. 同一知识点最多选 3 题
    3. 已成功召回 ≥3 次的题目自动排除
    4. 单次召回上限 20 题
    """
    now = datetime.now(UTC)
    
    # 基础查询条件: 未召回、未删除、召回次数小于阈值
    conditions = [
        ErrorBook.student_id == student_id,
        ErrorBook.is_deleted == False,  # noqa: E712
        ErrorBook.is_recalled == False,  # noqa: E712
        ErrorBook.recall_count < MAX_RECALL_COUNT_THRESHOLD,
    ]
    if subject_id is not None:
        conditions.append(ErrorBook.subject_id == subject_id)
    
    # 查询错题列表 (多查一些用于后续过滤)
    error_result = await db.execute(
        select(ErrorBook)
        .where(*conditions)
        .order_by(ErrorBook.created_at.desc())
        .limit(batch_size * 3)
    )
    errors = error_result.scalars().all()
    
    if not errors:
        return []
    
    # 收集所有涉及的知识点 ID
    all_kp_ids: set[int] = set()
    for error in errors:
        if error.knowledge_points:
            for kp in error.knowledge_points:
                if isinstance(kp, dict) and kp.get("id"):
                    all_kp_ids.add(int(kp["id"]))
                elif isinstance(kp, int):
                    all_kp_ids.add(kp)
    
    # 批量查询知识点重要性分数
    kp_importance_map: dict[int, float] = {}
    if all_kp_ids:
        kp_result = await db.execute(
            select(KnowledgeTree.id, KnowledgeTree.importance_score)
            .where(KnowledgeTree.id.in_(all_kp_ids))
        )
        for row in kp_result.all():
            kp_importance_map[row[0]] = float(row[1] or 0.5)
    
    # 批量查询学生知识点状态
    kp_status_map: dict[int, str] = {}
    if all_kp_ids:
        status_result = await db.execute(
            select(StudentKnowledgeStatus.knowledge_point_id, StudentKnowledgeStatus.status)
            .where(
                StudentKnowledgeStatus.student_id == student_id,
                StudentKnowledgeStatus.knowledge_point_id.in_(all_kp_ids),
            )
        )
        for row in status_result.all():
            kp_status_map[row[0]] = row[1]
    
    # 计算每道错题的优先级分数
    scored_errors: list[tuple[ErrorBook, float, int | None]] = []
    for error in errors:
        # 提取主要知识点 (第一个)
        primary_kp_id: int | None = None
        if error.knowledge_points:
            first_kp = error.knowledge_points[0]
            if isinstance(first_kp, dict) and first_kp.get("id"):
                primary_kp_id = int(first_kp["id"])
            elif isinstance(first_kp, int):
                primary_kp_id = first_kp
        
        # 获取知识点状态权重
        status = kp_status_map.get(primary_kp_id, "未观察") if primary_kp_id else "未观察"
        status_weight = STATUS_WEIGHT_MAP.get(status, 10)
        
        # 获取知识点重要性分数
        importance_score = kp_importance_map.get(primary_kp_id, 0.5) if primary_kp_id else 0.5
        
        # 计算天数
        days_since_error = (now - error.created_at).total_seconds() / 86400 if error.created_at else 0
        
        # 计算优先级分数
        priority_score = _calculate_priority_score(
            status_weight,
            days_since_error,
            importance_score,
            error.recall_count,
        )
        
        scored_errors.append((error, priority_score, primary_kp_id))
    
    # 按优先级分数降序排序
    scored_errors.sort(key=lambda x: x[1], reverse=True)
    
    # 根据规则选择错题
    selected: list[ErrorBook] = []
    kp_count: dict[int, int] = defaultdict(int)
    
    for error, score, primary_kp_id in scored_errors:
        if len(selected) >= batch_size:
            break
        
        # 检查同一知识点数量限制
        if primary_kp_id and kp_count[primary_kp_id] >= MAX_ERRORS_PER_KNOWLEDGE_POINT:
            continue
        
        selected.append(error)
        if primary_kp_id:
            kp_count[primary_kp_id] += 1
    
    return selected
