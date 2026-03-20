from __future__ import annotations

import ast
from collections.abc import AsyncGenerator
from typing import Any


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
    full_response = build_fallback_tutoring_response(message, knowledge_points)
    chunk_size = 24
    for start in range(0, len(full_response), chunk_size):
        yield full_response[start : start + chunk_size]
