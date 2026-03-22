from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.model_router import get_model_router
from app.llm.prompts import ROUTING_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Routing agent timeout in seconds
ROUTING_TIMEOUT_SECONDS = 10

DEFAULT_ROUTING_RESULT = {
    "intent": "ask",
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
    if session_context not in ("新会话", "new_session"):
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
    """Classify user intent with timeout protection and fallback.
    
    - Timeout: 10 seconds
    - Failure: Falls back to heuristic classification (default to "ask")
    """
    router = get_model_router()
    try:
        content, _meta = await asyncio.wait_for(
            router.invoke(
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
            ),
            timeout=ROUTING_TIMEOUT_SECONDS,
        )
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("routing response is not an object")
        return {
            "intent": data.get("intent", DEFAULT_ROUTING_RESULT["intent"]),
            "confidence": float(data.get("confidence", DEFAULT_ROUTING_RESULT["confidence"])),
            "route_to": data.get("route_to", DEFAULT_ROUTING_RESULT["route_to"]),
        }
    except asyncio.TimeoutError:
        logger.warning(
            "Routing Agent timeout after %ds, falling back to heuristic. "
            "student_id=%s, message_preview=%s",
            ROUTING_TIMEOUT_SECONDS,
            student_id,
            message[:50],
        )
        return _heuristic_intent(message, has_attachments, session_context)
    except Exception as exc:
        logger.warning(
            "Routing Agent failed, falling back to heuristic. "
            "student_id=%s, error=%s, message_preview=%s",
            student_id,
            str(exc),
            message[:50],
        )
        return _heuristic_intent(message, has_attachments, session_context)
