from __future__ import annotations

from typing import Protocol

from stt_quiz_service.schemas import (
    DailyTermCandidates,
    EvaluationSummary,
    QuizSet,
    StudyGuide,
    WeeklyGuide,
    WeeklyQuizSet,
    WeeklySelection,
    WeeklyTopicSet,
)
from stt_quiz_service.storage.repository import CorpusSelection
from stt_quiz_service.schemas import ChunkDocument


class GenerationBackend(Protocol):
    model_name: str

    def generate_quiz_set(
        self,
        lecture: CorpusSelection,
        chunks: list[ChunkDocument],
        *,
        mode: str,
        num_questions: int,
        choice_count: int | None,
    ) -> QuizSet: ...

    def generate_study_guide(
        self, lecture: CorpusSelection, chunks: list[ChunkDocument], *, mode: str
    ) -> StudyGuide: ...

    def evaluate(
        self,
        lecture: CorpusSelection,
        chunks: list[ChunkDocument],
        quiz_set: QuizSet,
        study_guide: StudyGuide,
        *,
        mode: str,
        latency_ms: int,
        token_cost_hint: float,
    ) -> EvaluationSummary: ...


class WeeklyGenerationBackend(Protocol):
    model_name: str

    def build_weekly_topic_set(
        self,
        week: WeeklySelection,
        candidate_terms: list[DailyTermCandidates],
        chunks: list[ChunkDocument],
    ) -> WeeklyTopicSet: ...

    def generate_weekly_guide(
        self,
        week: WeeklySelection,
        topic_set: WeeklyTopicSet,
        chunks: list[ChunkDocument],
    ) -> WeeklyGuide: ...

    def generate_weekly_quiz_set(
        self,
        week: WeeklySelection,
        topic_set: WeeklyTopicSet,
        chunks: list[ChunkDocument],
        *,
        num_questions: int,
    ) -> WeeklyQuizSet: ...
