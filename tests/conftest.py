from __future__ import annotations

from pathlib import Path

import pytest

from stt_quiz_service.config import Settings
from stt_quiz_service.orchestrator import WorkflowOrchestrator
from stt_quiz_service.storage.db import build_engine, build_session_factory
from stt_quiz_service.storage.repository import Repository


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'quizsvc.db'}",
        embedding_backend="hash",
        llm_backend="mock",
        transcripts_root=Path("NLP_Task2/강의 스크립트"),
        curriculum_path=Path("NLP_Task2/강의 커리큘럼.csv"),
    )


@pytest.fixture()
def orchestrator(settings: Settings) -> WorkflowOrchestrator:
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    repository = Repository(session_factory)
    orchestrator = WorkflowOrchestrator.build(settings, repository)
    orchestrator.bootstrap()
    return orchestrator
