import pytest

from app.llm.agents.tutoring import parse_tutoring_output, stream_fallback_tutoring_response


@pytest.mark.asyncio
async def test_parse_tutoring_output_extracts_metadata():
    content = (
        "先看已知条件，再列出不等式。\n"
        "---METADATA---\n"
        'knowledge_points: [{"id": 1, "name": "函数的定义域"}]\n'
        "strategy: hint\n"
        'follow_up_questions: ["下一步怎么列式？"]\n'
        "error_diagnosis: None\n"
        "---END---"
    )
    answer, metadata = parse_tutoring_output(content)
    assert "先看已知条件" in answer
    assert metadata["strategy"] == "hint"
    assert metadata["knowledge_points"][0]["name"] == "函数的定义域"


@pytest.mark.asyncio
async def test_fallback_tutoring_stream_contains_metadata():
    chunks = []
    async for chunk in stream_fallback_tutoring_response("我不会这道题"):
        chunks.append(chunk)
    full = "".join(chunks)
    assert "---METADATA---" in full
    assert "follow_up_questions" in full
