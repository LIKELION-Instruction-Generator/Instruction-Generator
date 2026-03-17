from __future__ import annotations

from types import SimpleNamespace

import pytest

from stt_quiz_service.agents.pydantic_ai_backend import PydanticAIBackend
from stt_quiz_service.schemas import ChunkDocument, QuizSet
from stt_quiz_service.storage.repository import CorpusSelection


def test_generate_quiz_set_rejects_empty_items():
    backend = PydanticAIBackend.__new__(PydanticAIBackend)
    backend.model_name = "test-model"
    backend.quiz_agent = SimpleNamespace(
        run_sync=lambda prompt: SimpleNamespace(
            output=QuizSet(corpus_id="2026-02-02", mode="rag", items=[], model_info={})
        )
    )

    lecture = CorpusSelection(
        corpus_id="2026-02-02",
        date="2026-02-02",
        subject="subject",
        content="content",
        learning_goal="goal",
        summary="summary",
        topic_count=1,
    )
    chunks = [
        ChunkDocument(
            chunk_id="c1",
            corpus_id="2026-02-02",
            chunk_order=0,
            text="context",
            source_span="0-1",
            metadata={},
        )
    ]

    with pytest.raises(ValueError, match="Invalid quiz size"):
        backend.generate_quiz_set(lecture, chunks, mode="rag", num_questions=5, choice_count=4)
