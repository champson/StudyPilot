from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.model_router import get_model_router
from app.llm.prompts import ASSESSMENT_SYSTEM_PROMPT


def _infer_outcome(messages: list[dict[str, Any]]) -> tuple[str, str | None]:
    user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]
    last_user = user_messages[-1] if user_messages else ""
    if any(token in last_user for token in ("不会", "不懂", "不知道", "没思路", "放弃")):
        return "incorrect", "概念不清"
    if any(token in last_user for token in ("明白", "懂了", "应该", "是不是", "可以")):
        return "correct_with_hint", None
    return "incorrect", "概念不清"


def build_fallback_assessment(
    *,
    subject_id: int | None,
    messages: list[dict[str, Any]],
    knowledge_points_involved: list[dict[str, Any]],
) -> dict[str, Any]:
    outcome, error_type = _infer_outcome(messages)
    updates = []
    for kp in knowledge_points_involved:
        current_status = kp.get("current_status") or "未观察"
        if outcome == "correct_with_hint":
            new_status = "需要巩固"
            reason = "经提示后答对"
        else:
            new_status = "初步接触" if current_status == "未观察" else "需要巩固"
            reason = "答疑中暴露薄弱点"
        updates.append(
            {
                "knowledge_point_id": kp.get("id"),
                "knowledge_point_name": kp.get("name"),
                "previous_status": current_status,
                "new_status": new_status,
                "reason": reason,
                "confidence": 0.75,
            }
        )

    error_book_entries = []
    if outcome == "incorrect" and knowledge_points_involved:
        error_book_entries.append(
            {
                "subject_id": subject_id,
                "question_summary": messages[-1]["content"][:80] if messages else "答疑错题",
                "knowledge_point_ids": [
                    kp.get("id")
                    for kp in knowledge_points_involved
                    if kp.get("id")
                ],
                "error_type": error_type or "概念不清",
                "entry_reason": "wrong",
            }
        )

    return {
        "knowledge_point_updates": updates,
        "session_summary": {
            "total_questions": len([m for m in messages if m.get("role") == "user"]),
            "correct_first_try": 0,
            "correct_with_hint": 1 if outcome == "correct_with_hint" else 0,
            "incorrect": 1 if outcome == "incorrect" else 0,
            "dominant_error_type": error_type,
        },
        "error_book_entries": error_book_entries,
        "suggested_followup": "建议明天回顾本次答疑涉及的核心知识点。",
    }


async def assess_session(
    *,
    subject_id: int | None,
    messages: list[dict[str, Any]],
    knowledge_points_involved: list[dict[str, Any]],
    db: AsyncSession | None = None,
    student_id: int | None = None,
) -> dict[str, Any]:
    router = get_model_router()
    payload = {
        "subject_id": subject_id,
        "messages": messages,
        "knowledge_points_involved": knowledge_points_involved,
    }
    try:
        content, _meta = await router.invoke(
            "assessment",
            [
                {"role": "system", "content": ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            db=db,
            student_id=student_id,
            response_format={"type": "json_object"},
            max_tokens=1200,
        )
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("assessment payload is not an object")
        return data
    except Exception:
        return build_fallback_assessment(
            subject_id=subject_id,
            messages=messages,
            knowledge_points_involved=knowledge_points_involved,
        )
