import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.agents.extraction import extract_questions_from_upload
from app.models.upload import StudyUpload
from app.tasks.ocr import run_ocr_pipeline


@pytest.mark.asyncio
async def test_extraction_agent_fallback_reads_local_text(tmp_path: Path):
    file_path = tmp_path / "question.txt"
    file_path.write_text("求函数 f(x)=x^2 在 x=2 处的导数", encoding="utf-8")

    result = await extract_questions_from_upload(
        file_path=str(file_path),
        subject_id=2,
        subject_name="数学",
    )
    assert result["detected_subject"] == "数学"
    assert result["questions"]


@pytest.mark.asyncio
async def test_extraction_agent_sends_file_content_to_model(tmp_path: Path, monkeypatch):
    file_path = tmp_path / "question.png"
    file_path.write_bytes(b"fake-image-bytes")
    captured = {}

    class FakeRouter:
        async def invoke(self, agent, messages, **kwargs):
            captured["agent"] = agent
            captured["messages"] = messages
            return json.dumps({"detected_subject": "数学", "questions": [], "raw_text": ""}), {}

    monkeypatch.setattr(
        "app.llm.agents.extraction.get_model_router",
        lambda: FakeRouter(),
    )

    await extract_questions_from_upload(
        file_path=str(file_path),
        subject_id=2,
        subject_name="数学",
    )

    user_content = captured["messages"][1]["content"]
    assert captured["agent"] == "extraction"
    assert isinstance(user_content, list)
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_run_ocr_pipeline_updates_upload(
    db_session: AsyncSession, seed_data: dict, tmp_path: Path
):
    file_path = tmp_path / "ocr-source.txt"
    file_path.write_text("函数的定义域练习题", encoding="utf-8")

    upload = StudyUpload(
        student_id=seed_data["profile"].id,
        upload_type="homework",
        file_hash="hash",
        original_url=str(file_path),
        subject_id=seed_data["subjects"][1].id,
        ocr_status="pending",
    )
    db_session.add(upload)
    await db_session.flush()
    await db_session.commit()

    await run_ocr_pipeline(upload.id)
    await db_session.refresh(upload)

    result = await db_session.execute(select(StudyUpload).where(StudyUpload.id == upload.id))
    refreshed = result.scalar_one()
    assert refreshed.ocr_status == "completed"
    assert refreshed.ocr_result is not None
