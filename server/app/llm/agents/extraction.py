from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.model_router import get_model_router
from app.llm.prompts import EXTRACTION_SYSTEM_PROMPT


def build_fallback_extraction(
    *,
    file_path: str,
    subject_id: int | None,
    subject_name: str | None,
) -> dict[str, Any]:
    path = Path(file_path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception:
        raw_text = ""

    question_text = raw_text.strip() or "无法直接读取文本内容，请人工确认题目结构。"
    return {
        "detected_subject": subject_name or "未知学科",
        "detected_subject_id": subject_id,
        "questions": [
            {
                "index": 1,
                "type": "unknown",
                "content_text": question_text[:300],
                "content_latex": None,
                "options": None,
                "answer": None,
                "knowledge_points": [],
            }
        ],
        "raw_text": question_text[:1000],
    }


def _read_file_payload(file_path: str) -> tuple[bytes | None, str]:
    path = Path(file_path)
    try:
        return path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    except Exception:
        return None, "application/octet-stream"


def _build_user_content(
    *,
    file_path: str,
    subject_id: int | None,
    subject_name: str | None,
) -> str | list[dict[str, Any]]:
    file_bytes, mime_type = _read_file_payload(file_path)
    base_payload = {
        "file_path": file_path,
        "file_name": Path(file_path).name,
        "mime_type": mime_type,
        "subject_id_hint": subject_id,
        "subject_name_hint": subject_name,
    }
    if file_bytes is None:
        return json.dumps(base_payload, ensure_ascii=False)

    if mime_type.startswith("image/"):
        data_url = f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode('ascii')}"
        return [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        **base_payload,
                        "instruction": "请结合图片内容识别题目、学科和知识点，输出 JSON。",
                    },
                    ensure_ascii=False,
                ),
            },
            {"type": "image_url", "image_url": {"url": data_url}},
        ]

    text_preview = None
    try:
        text_preview = file_bytes.decode("utf-8")
    except Exception:
        text_preview = None

    return json.dumps(
        {
            **base_payload,
            "text_preview": text_preview[:8000] if text_preview else None,
            "file_base64": base64.b64encode(file_bytes).decode("ascii"),
        },
        ensure_ascii=False,
    )


async def extract_questions_from_upload(
    *,
    file_path: str,
    subject_id: int | None,
    subject_name: str | None,
    db: AsyncSession | None = None,
    student_id: int | None = None,
) -> dict[str, Any]:
    router = get_model_router()
    try:
        content, _meta = await router.invoke(
            "extraction",
            [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_user_content(
                        file_path=file_path,
                        subject_id=subject_id,
                        subject_name=subject_name,
                    ),
                },
            ],
            db=db,
            student_id=student_id,
            response_format={"type": "json_object"},
            max_tokens=1200,
        )
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("extraction payload is not an object")
        return data
    except Exception:
        return build_fallback_extraction(
            file_path=file_path,
            subject_id=subject_id,
            subject_name=subject_name,
        )
