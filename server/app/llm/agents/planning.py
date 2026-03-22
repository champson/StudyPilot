from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.model_router import get_model_router
from app.llm.prompts import PLANNING_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Fallback plan template used when Planning Agent fails
GENERIC_FALLBACK_PLAN = {
    "recommended_subjects": [],
    "tasks": [],
    "generation_context": {
        "source": "generic_fallback",
        "reason": "planning_agent_failed",
    },
}


def _subject_limit(available_minutes: int) -> int:
    if available_minutes < 30:
        return 1
    if available_minutes <= 60:
        return 2
    return 3


def rule_based_ranking(context: dict[str, Any]) -> list[dict[str, Any]]:
    subjects = {item["subject_id"]: dict(item) for item in context.get("subjects", [])}
    scores: dict[int, dict[str, Any]] = {
        item["subject_id"]: {
            "subject_id": item["subject_id"],
            "subject_name": item["subject_name"],
            "score": 0,
            "reasons": [],
        }
        for item in context.get("subjects", [])
    }
    mode = context.get("learning_mode", "workday_follow")

    for upload in context.get("recent_uploads", []):
        row = scores.get(upload["subject_id"])
        if row:
            row["score"] += 30 if mode == "workday_follow" else 10
            row["reasons"].append("今日校内同步")

    for error in context.get("recent_errors", []):
        row = scores.get(error["subject_id"])
        if row:
            row["score"] += min(error.get("error_count", 1) * 8, 24)
            row["reasons"].append("今日错误较多" if mode == "workday_follow" else "本周错题修复")

    for exam in context.get("upcoming_exams", []):
        row = scores.get(exam["subject_id"])
        if row:
            row["score"] += 18
            row["reasons"].append("考试临近")

    for risk in context.get("subject_risks", []):
        row = scores.get(risk["subject_id"])
        if not row:
            continue
        level = risk.get("risk_level", "稳定")
        if level == "高风险":
            row["score"] += 25
        elif level == "中度风险":
            row["score"] += 18
        elif level == "轻度风险":
            row["score"] += 10
        if level != "稳定":
            row["reasons"].append("薄弱知识点待修复")

    for mastery in context.get("knowledge_mastery", []):
        row = scores.get(mastery["subject_id"])
        if row and mastery.get("repeated_mistakes", 0) > 0:
            row["score"] += mastery["repeated_mistakes"] * 6
            row["reasons"].append("近期反复错误")

    ranked = sorted(scores.values(), key=lambda item: (-item["score"], item["subject_id"]))
    for item in ranked:
        if not item["reasons"]:
            item["reasons"] = ["本周覆盖不足"]
        item["reasons"] = list(dict.fromkeys(item["reasons"]))
        item["subject_name"] = subjects[item["subject_id"]]["subject_name"]
    return ranked


def build_fallback_plan(
    context: dict[str, Any], *, error_reason: str | None = None
) -> dict[str, Any]:
    """Build fallback plan when LLM fails.

    Returns a rule-based plan with generation_context indicating fallback source.
    """
    ranked = rule_based_ranking(context)
    if not ranked:
        # No subjects available, return generic fallback
        logger.warning(
            "Planning Agent fallback: no subjects available, returning generic fallback"
        )
        return {
            **GENERIC_FALLBACK_PLAN,
            "reasoning": error_reason or "LLM 不可用，无可用学科。",
        }

    selected = ranked[: _subject_limit(context.get("available_minutes", 120))]
    tasks: list[dict[str, Any]] = []
    sequence = 1

    for item in selected:
        related_errors = [
            error
            for error in context.get("recent_errors", [])
            if error["subject_id"] == item["subject_id"]
        ]
        error_count = sum(error.get("error_count", 0) for error in related_errors)
        if error_count > 0:
            tasks.append(
                {
                    "subject_id": item["subject_id"],
                    "task_type": "error_review",
                    "title": f"{item['subject_name']}错题回顾",
                    "description": (
                        f"回顾近期 {error_count} 个高频错误点，"
                        "先说思路再做 1-2 题自检。"
                    ),
                    "knowledge_points": [
                        error.get("knowledge_point_id")
                        for error in related_errors
                        if error.get("knowledge_point_id") is not None
                    ],
                    "sequence": sequence,
                    "estimated_minutes": 30 if sequence == 1 else 20,
                    "difficulty": "medium",
                }
            )
        else:
            tasks.append(
                {
                    "subject_id": item["subject_id"],
                    "task_type": "consolidation",
                    "title": f"{item['subject_name']}重点巩固",
                    "description": "围绕本周薄弱点做一轮巩固，整理 3 个关键知识点。",
                    "knowledge_points": [],
                    "sequence": sequence,
                    "estimated_minutes": 25 if sequence == 1 else 20,
                    "difficulty": "low" if sequence > 1 else "medium",
                }
            )
        sequence += 1

    reasoning = "；".join(
        f"{item['subject_name']}：{'、'.join(item['reasons'])}" for item in selected
    )
    return {
        "recommended_subjects": [
            {
                "subject_id": item["subject_id"],
                "subject_name": item["subject_name"],
                "reasons": item["reasons"],
            }
            for item in selected
        ],
        "tasks": tasks,
        "reasoning": reasoning or "使用规则引擎生成保底计划。",
        "generation_context": {
            "source": "rule_based_fallback",
            "reason": error_reason or "planning_agent_unavailable",
        },
    }


async def generate_plan_payload(
    context: dict[str, Any],
    *,
    db: AsyncSession | None = None,
    student_id: int | None = None,
) -> dict[str, Any]:
    """Generate learning plan using LLM.

    On failure:
    - Returns rule-based fallback plan with generation_context
    - Does not raise exception
    """
    router = get_model_router()
    ranked = rule_based_ranking(context)
    prompt_payload = dict(context)
    prompt_payload["ranked_subjects"] = ranked

    try:
        content, _meta = await router.invoke(
            "planning",
            [
                {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
            ],
            db=db,
            student_id=student_id,
            response_format={"type": "json_object"},
            max_tokens=1200,
        )
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("planning payload is not an object")
        recommended_subjects = data.get("recommended_subjects") or []
        tasks = data.get("tasks") or []
        if not isinstance(recommended_subjects, list) or not isinstance(tasks, list):
            raise ValueError("planning payload missing required arrays")
        if len(recommended_subjects) > 3:
            recommended_subjects = recommended_subjects[:3]
        return {
            "recommended_subjects": recommended_subjects,
            "tasks": tasks,
            "reasoning": data.get("reasoning", ""),
            "generation_context": {
                "source": "llm_generated",
                "reason": None,
            },
        }
    except Exception as exc:
        error_message = str(exc)
        logger.warning(
            "Planning Agent failed, using fallback. "
            "student_id=%s, error=%s",
            student_id,
            error_message,
        )
        return build_fallback_plan(context, error_reason=error_message)
