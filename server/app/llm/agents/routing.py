from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.model_router import get_model_router
from app.llm.prompts import ROUTING_SYSTEM_PROMPT

DEFAULT_ROUTING_RESULT = {
    "intent": "ask_question",
    "confidence": 0.5,
    "route_to": "tutoring",
}


def _heuristic_intent(
    message: str, has_attachments: bool, session_context: str
) -> dict[str, Any]:
    lower = message.lower()
    if has_attachments:
        return {"intent": "upload_question", "confidence": 0.9, "route_to": "tutoring"}
    if any(token in message for token in ("切换模式", "标记完成", "修改计划")):
        return {"intent": "operate", "confidence": 0.8, "route_to": "none"}
    if any(token in lower for token in ("你好", "在吗", "哈哈", "天气")):
        return {"intent": "chat", "confidence": 0.7, "route_to": "none"}
    if session_context != "新会话":
        return {"intent": "follow_up", "confidence": 0.7, "route_to": "tutoring"}
    return DEFAULT_ROUTING_RESULT.copy()


async def classify_intent(
    *,
    message: str,
    has_attachments: bool,
    session_context: str,
    db: AsyncSession | None = None,
    student_id: int | None = None,
) -> dict[str, Any]:
    router = get_model_router()
    try:
        content, _meta = await router.invoke(
            "routing",
            [
                {"role": "system", "content": ROUTING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "message": message,
                            "has_attachments": has_attachments,
                            "session_context": session_context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            db=db,
            student_id=student_id,
            response_format={"type": "json_object"},
        )
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("routing response is not an object")
        return {
            "intent": data.get("intent", DEFAULT_ROUTING_RESULT["intent"]),
            "confidence": float(data.get("confidence", DEFAULT_ROUTING_RESULT["confidence"])),
            "route_to": data.get("route_to", DEFAULT_ROUTING_RESULT["route_to"]),
        }
    except Exception:
        return _heuristic_intent(message, has_attachments, session_context)
