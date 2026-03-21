from __future__ import annotations

import ast
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)

# Tutoring agent timeout in seconds
TUTORING_TIMEOUT_SECONDS = 60

# SSE error event codes
TUTORING_TIMEOUT_CODE = "TUTORING_TIMEOUT"
TUTORING_ERROR_CODE = "TUTORING_ERROR"


def _parse_metadata_value(raw: str) -> Any:
    text = raw.strip()
    if text in {"null", "None"}:
        return None
    if text in {"true", "false"}:
        return text == "true"
    try:
        return ast.literal_eval(text)
    except Exception:
        return text


def parse_tutoring_output(content: str) -> tuple[str, dict[str, Any]]:
    metadata = {
        "knowledge_points": [],
        "strategy": "hint",
        "follow_up_questions": [],
        "error_diagnosis": None,
    }
    if "---METADATA---" not in content:
        return content.strip(), metadata

    answer_part, rest = content.split("---METADATA---", 1)
    meta_part, _separator, _tail = rest.partition("---END---")
    for line in meta_part.strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in metadata:
            metadata[key] = _parse_metadata_value(value)
    return answer_part.strip(), metadata


def build_fallback_tutoring_response(
    message: str,
    knowledge_points: list[dict[str, Any]] | None = None,
    *,
    strategy: str = "hint",
) -> str:
    knowledge_points = knowledge_points or []
    kp_text = knowledge_points or [{"id": 0, "name": "解题思路"}]
    answer = (
        "先别急着直接求答案，我们先把题目条件拆开。"
        "你先说说题目已知了什么、要求你求什么，我再带你走下一步。"
    )
    if any(token in message for token in ("不会", "不懂", "卡住")):
        answer += " 如果完全没思路，可以先从定义、公式或已知条件里找一个能下手的点。"
    return (
        f"{answer}\n"
        "---METADATA---\n"
        f"knowledge_points: {kp_text}\n"
        f"strategy: {strategy}\n"
        'follow_up_questions: ["这道题的已知条件是什么？", "你准备先用哪个公式或定义？"]\n'
        "error_diagnosis: None\n"
        "---END---"
    )


async def stream_fallback_tutoring_response(
    message: str, knowledge_points: list[dict[str, Any]] | None = None
) -> AsyncGenerator[str, None]:
    """Stream a fallback tutoring response when LLM is unavailable."""
    full_response = build_fallback_tutoring_response(message, knowledge_points)
    chunk_size = 24
    for start in range(0, len(full_response), chunk_size):
        yield full_response[start : start + chunk_size]


def build_tutoring_error_event(
    code: str,
    message: str,
    *,
    student_id: int | None = None,
    session_id: int | None = None,
    original_error: str | None = None,
) -> dict[str, Any]:
    """Build SSE error event for tutoring failures.
    
    Codes:
    - TUTORING_TIMEOUT: Request timed out
    - TUTORING_ERROR: Other errors
    """
    error_event = {
        "type": "error",
        "code": code,
        "message": message,
    }
    
    # Log the error with context
    logger.warning(
        "Tutoring Agent error: code=%s, student_id=%s, session_id=%s, error=%s",
        code,
        student_id,
        session_id,
        original_error or message,
    )
    
    return error_event


def build_tutoring_timeout_error(
    *,
    student_id: int | None = None,
    session_id: int | None = None,
) -> dict[str, Any]:
    """Build SSE error event for tutoring timeout."""
    return build_tutoring_error_event(
        TUTORING_TIMEOUT_CODE,
        "答疑服务暂时繁忙，请稍后重试",
        student_id=student_id,
        session_id=session_id,
        original_error=f"Timeout after {TUTORING_TIMEOUT_SECONDS}s",
    )


def build_tutoring_friendly_error(
    *,
    student_id: int | None = None,
    session_id: int | None = None,
    original_error: str | None = None,
) -> dict[str, Any]:
    """Build SSE error event for tutoring errors (friendly message, not 500)."""
    return build_tutoring_error_event(
        TUTORING_ERROR_CODE,
        "答疑服务出现问题，请稍后重试",
        student_id=student_id,
        session_id=session_id,
        original_error=original_error,
    )


def format_sse_error_event(error_event: dict[str, Any]) -> str:
    """Format error event as SSE event string."""
    return f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"
