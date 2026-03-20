import hashlib
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_book import ErrorBook
from app.models.knowledge import KnowledgeTree, KnowledgeUpdateLog, StudentKnowledgeStatus
from app.models.qa import QaSession
from app.models.report import SubjectRiskState
from app.models.subject import Subject

NOT_OBSERVED = "未观察"
INITIAL_CONTACT = "初步接触"
NEEDS_CONSOLIDATION = "需要巩固"
BASICALLY_MASTERED = "基本掌握"
REPEATED_MISTAKES = "反复失误"

STABLE = "稳定"
LIGHT_RISK = "轻度风险"
MEDIUM_RISK = "中度风险"
HIGH_RISK = "高风险"


def current_week_string(target_date: date | None = None) -> str:
    target_date = target_date or date.today()
    iso = target_date.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


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


async def aggregate_knowledge_mastery_by_subject(
    db: AsyncSession, student_id: int
) -> list[dict[str, Any]]:
    query = (
        select(
            KnowledgeTree.subject_id,
            Subject.name,
            StudentKnowledgeStatus.status,
            func.count(StudentKnowledgeStatus.id),
        )
        .join(
            KnowledgeTree,
            StudentKnowledgeStatus.knowledge_point_id == KnowledgeTree.id,
        )
        .join(Subject, KnowledgeTree.subject_id == Subject.id)
        .where(StudentKnowledgeStatus.student_id == student_id)
        .group_by(KnowledgeTree.subject_id, Subject.name, StudentKnowledgeStatus.status)
    )
    result = await db.execute(query)

    grouped: dict[int, dict[str, Any]] = {}
    for subject_id, subject_name, status, count in result.all():
        row = grouped.setdefault(
            subject_id,
            {
                "subject_id": subject_id,
                "subject_name": subject_name,
                "mastered": 0,
                "needs_consolidation": 0,
                "repeated_mistakes": 0,
            },
        )
        if status == BASICALLY_MASTERED:
            row["mastered"] += count
        elif status == REPEATED_MISTAKES:
            row["repeated_mistakes"] += count
        elif status in {INITIAL_CONTACT, NEEDS_CONSOLIDATION}:
            row["needs_consolidation"] += count
    return list(grouped.values())


async def resolve_knowledge_points_by_names(
    db: AsyncSession, names: list[str], subject_id: int | None = None
) -> list[dict[str, Any]]:
    if not names:
        return []
    query = select(KnowledgeTree).where(KnowledgeTree.name.in_(names))
    if subject_id is not None:
        query = query.where(KnowledgeTree.subject_id == subject_id)
    result = await db.execute(query)
    points = result.scalars().all()
    by_name = {point.name: point for point in points}
    return [
        {"id": by_name[name].id, "name": by_name[name].name}
        for name in names
        if name in by_name
    ]


async def get_status_snapshot(
    db: AsyncSession, student_id: int, knowledge_point_ids: list[int]
) -> dict[int, str]:
    if not knowledge_point_ids:
        return {}
    result = await db.execute(
        select(StudentKnowledgeStatus).where(
            StudentKnowledgeStatus.student_id == student_id,
            StudentKnowledgeStatus.knowledge_point_id.in_(knowledge_point_ids),
        )
    )
    return {
        item.knowledge_point_id: item.status for item in result.scalars().all()
    }


async def batch_init_from_onboarding(
    db: AsyncSession,
    *,
    student_id: int,
    weak_subject_ids: list[int],
    recent_exam_scores: dict[int, float] | None = None,
) -> dict[str, Any]:
    recent_exam_scores = recent_exam_scores or {}
    initialized_points = 0

    if weak_subject_ids:
        existing_result = await db.execute(
            select(StudentKnowledgeStatus.knowledge_point_id).where(
                StudentKnowledgeStatus.student_id == student_id
            )
        )
        existing_ids = {row[0] for row in existing_result.all()}

        point_result = await db.execute(
            select(KnowledgeTree).where(
                KnowledgeTree.subject_id.in_(weak_subject_ids),
                KnowledgeTree.level <= 2,
            )
        )
        for point in point_result.scalars().all():
            if point.id in existing_ids:
                continue
            status = StudentKnowledgeStatus(
                student_id=student_id,
                knowledge_point_id=point.id,
                status=INITIAL_CONTACT,
                last_update_reason="onboarding_weak_subject",
            )
            db.add(status)
            db.add(
                KnowledgeUpdateLog(
                    student_id=student_id,
                    knowledge_point_id=point.id,
                    previous_status=None,
                    new_status=INITIAL_CONTACT,
                    trigger_type="onboarding",
                    trigger_detail={"reason": "weak_subject"},
                )
            )
            initialized_points += 1

    subject_result = await db.execute(
        select(Subject).where(
            Subject.id.in_(set(weak_subject_ids) | set(recent_exam_scores.keys()))
        )
    )
    subject_map = {subject.id: subject for subject in subject_result.scalars().all()}

    week = current_week_string()
    existing_risk_result = await db.execute(
        select(SubjectRiskState).where(
            SubjectRiskState.student_id == student_id,
            SubjectRiskState.effective_week == week,
        )
    )
    existing_risks = {
        risk.subject_id: risk for risk in existing_risk_result.scalars().all()
    }

    initialized_subject_risks: list[dict[str, Any]] = []
    candidate_subject_ids = set(weak_subject_ids) | set(recent_exam_scores.keys())
    for subject_id in candidate_subject_ids:
        risk_level: str | None = None
        score = recent_exam_scores.get(subject_id)
        if score is not None:
            if score < 60:
                risk_level = MEDIUM_RISK
            elif score < 75:
                risk_level = LIGHT_RISK
        elif subject_id in weak_subject_ids:
            risk_level = LIGHT_RISK

        if risk_level is None:
            continue

        record = existing_risks.get(subject_id)
        if record is None:
            record = SubjectRiskState(
                student_id=student_id,
                subject_id=subject_id,
                risk_level=risk_level,
                effective_week=week,
                calculation_detail={"source": "onboarding"},
            )
            db.add(record)
        else:
            record.risk_level = risk_level
            record.calculation_detail = {"source": "onboarding"}

        subject = subject_map.get(subject_id)
        initialized_subject_risks.append(
            {
                "subject_id": subject_id,
                "subject_code": subject.code if subject else str(subject_id),
                "risk_level": risk_level,
            }
        )

    await db.flush()
    return {
        "initialized_knowledge_points": initialized_points,
        "initialized_subject_risks": initialized_subject_risks,
    }


async def _count_prior_success_sessions(
    db: AsyncSession, student_id: int, knowledge_point_id: int
) -> set[int]:
    result = await db.execute(
        select(KnowledgeUpdateLog.trigger_detail).where(
            KnowledgeUpdateLog.student_id == student_id,
            KnowledgeUpdateLog.knowledge_point_id == knowledge_point_id,
            KnowledgeUpdateLog.trigger_type.in_(
                ["correct_first_try", "correct_with_hint", "recall_success"]
            ),
        )
    )
    session_ids: set[int] = set()
    for detail in result.scalars().all():
        if isinstance(detail, dict) and detail.get("session_id") is not None:
            session_ids.add(int(detail["session_id"]))
    return session_ids


async def _count_prior_recall_failures(
    db: AsyncSession, student_id: int, knowledge_point_id: int
) -> int:
    result = await db.execute(
        select(func.count(KnowledgeUpdateLog.id)).where(
            KnowledgeUpdateLog.student_id == student_id,
            KnowledgeUpdateLog.knowledge_point_id == knowledge_point_id,
            KnowledgeUpdateLog.trigger_type == "recall_fail",
        )
    )
    return int(result.scalar() or 0)


async def update_mastery_state(
    db: AsyncSession,
    *,
    student_id: int,
    knowledge_point_id: int,
    outcome: str,
    session_id: int | None,
    reason: str,
    confidence: float | None = None,
) -> StudentKnowledgeStatus:
    result = await db.execute(
        select(StudentKnowledgeStatus).where(
            StudentKnowledgeStatus.student_id == student_id,
            StudentKnowledgeStatus.knowledge_point_id == knowledge_point_id,
        )
    )
    status = result.scalar_one_or_none()
    previous_status = status.status if status else NOT_OBSERVED

    if outcome == "correct_first_try":
        success_sessions = await _count_prior_success_sessions(db, student_id, knowledge_point_id)
        if previous_status in {NEEDS_CONSOLIDATION, BASICALLY_MASTERED} and (
            session_id is not None
            and session_id not in success_sessions
            and len(success_sessions) >= 1
        ):
            new_status = BASICALLY_MASTERED
        elif previous_status == REPEATED_MISTAKES:
            new_status = NEEDS_CONSOLIDATION
        else:
            new_status = NEEDS_CONSOLIDATION
    elif outcome == "correct_with_hint":
        new_status = (
            BASICALLY_MASTERED
            if previous_status == BASICALLY_MASTERED
            else NEEDS_CONSOLIDATION
        )
    elif outcome == "recall_success":
        new_status = BASICALLY_MASTERED if previous_status != NOT_OBSERVED else NEEDS_CONSOLIDATION
    elif outcome == "recall_fail":
        prior_failures = await _count_prior_recall_failures(db, student_id, knowledge_point_id)
        if prior_failures >= 1:
            new_status = REPEATED_MISTAKES
        else:
            new_status = INITIAL_CONTACT if previous_status == NOT_OBSERVED else NEEDS_CONSOLIDATION
    else:
        new_status = INITIAL_CONTACT if previous_status == NOT_OBSERVED else NEEDS_CONSOLIDATION

    now = datetime.now(UTC)
    if status is None:
        status = StudentKnowledgeStatus(
            student_id=student_id,
            knowledge_point_id=knowledge_point_id,
            status=new_status,
            last_update_reason=reason,
            last_updated_at=now,
        )
        db.add(status)
    else:
        status.status = new_status
        status.last_update_reason = reason
        status.last_updated_at = now

    db.add(
        KnowledgeUpdateLog(
            student_id=student_id,
            knowledge_point_id=knowledge_point_id,
            previous_status=(
                None
                if previous_status == NOT_OBSERVED and status.id is None
                else previous_status
            ),
            new_status=new_status,
            trigger_type=outcome,
            trigger_detail={
                "session_id": session_id,
                "reason": reason,
                "confidence": confidence,
            },
        )
    )
    await db.flush()
    return status


def _assessment_outcome(update: dict[str, Any], summary: dict[str, Any]) -> str:
    reason = str(update.get("reason", ""))
    if "提示" in reason:
        return "correct_with_hint"
    if summary.get("correct_first_try", 0) > 0:
        return "correct_first_try"
    if summary.get("correct_with_hint", 0) > 0:
        return "correct_with_hint"
    return "incorrect"


async def apply_assessment_results(
    db: AsyncSession,
    *,
    student_id: int,
    session: QaSession,
    assessment: dict[str, Any],
) -> None:
    summary = assessment.get("session_summary") or {}

    for update in assessment.get("knowledge_point_updates", []):
        knowledge_point_id = update.get("knowledge_point_id")
        if knowledge_point_id is None:
            continue
        await update_mastery_state(
            db,
            student_id=student_id,
            knowledge_point_id=int(knowledge_point_id),
            outcome=_assessment_outcome(update, summary),
            session_id=session.id,
            reason=update.get("reason", "assessment"),
            confidence=update.get("confidence"),
        )

    for entry in assessment.get("error_book_entries", []):
        subject_id = entry.get("subject_id")
        if subject_id is None:
            continue
        summary_text = str(entry.get("question_summary") or "答疑错题").strip()
        content_hash = hashlib.sha256(
            f"{student_id}:{subject_id}:{summary_text}".encode()
        ).hexdigest()
        existing = await db.execute(
            select(ErrorBook).where(
                ErrorBook.student_id == student_id,
                ErrorBook.content_hash == content_hash,
            )
        )
        if existing.scalar_one_or_none():
            continue
        db.add(
            ErrorBook(
                student_id=student_id,
                subject_id=int(subject_id),
                question_content={"summary": summary_text},
                knowledge_points=[
                    {"id": kp_id}
                    for kp_id in entry.get("knowledge_point_ids", [])
                    if kp_id is not None
                ],
                error_type=entry.get("error_type"),
                entry_reason=entry.get("entry_reason", "wrong"),
                content_hash=content_hash,
                is_explained=True,
            )
        )

    session.structured_summary = {
        **summary,
        "suggested_followup": assessment.get("suggested_followup"),
    }
    await db.flush()
