from __future__ import annotations

from pydantic_ai import Agent

from stt_quiz_service.agents.base import GenerationBackend
from stt_quiz_service.config import Settings
from stt_quiz_service.prompts import read_prompt_section
from stt_quiz_service.schemas import (
    ChunkDocument,
    EvaluationSummary,
    QuizSet,
    StudyGuide,
)
from stt_quiz_service.storage.repository import CorpusSelection
from stt_quiz_service.services.retrieval import extract_concepts
from stt_quiz_service.services.quiz_profiles import (
    build_profile_plan,
    downgrade_weak_retests,
    validate_quiz_items,
)

class PydanticAIBackend(GenerationBackend):
    def __init__(self, settings: Settings):
        self.model_name = settings.default_model
        shared = read_prompt_section("Shared Rules")
        quiz_prompt = f"{shared}\n\n{read_prompt_section('Quiz Generation System Prompt')}"
        guide_prompt = f"{shared}\n\n{read_prompt_section('Study Guide System Prompt')}"
        eval_prompt = f"{shared}\n\n{read_prompt_section('Evaluation System Prompt')}"
        self.quiz_agent = Agent(
            self.model_name,
            output_type=QuizSet,
            system_prompt=quiz_prompt,
        )
        self.guide_agent = Agent(
            self.model_name,
            output_type=StudyGuide,
            system_prompt=guide_prompt,
        )
        self.eval_agent = Agent(
            self.model_name,
            output_type=EvaluationSummary,
            system_prompt=eval_prompt,
        )

    def generate_quiz_set(
        self,
        lecture: CorpusSelection,
        chunks: list[ChunkDocument],
        *,
        mode: str,
        num_questions: int,
        choice_count: int | None,
    ) -> QuizSet:
        profile_plan = build_profile_plan(
            lecture,
            chunks,
            num_questions=num_questions,
            preferred_choice_count=choice_count,
        )
        prompt = self._build_generation_prompt(
            lecture,
            chunks,
            mode,
            num_questions,
            choice_count,
            eligible_profiles=profile_plan["eligible_profiles"],
            profile_counts=profile_plan["profile_counts"],
            profile_sequence=profile_plan["profile_sequence"],
        )
        result = self.quiz_agent.run_sync(prompt).output
        normalized_items, adjusted_profile_counts = downgrade_weak_retests(
            result.items,
            eligible_profiles=profile_plan["eligible_profiles"],
            expected_profile_counts=profile_plan["profile_counts"],
        )
        result = result.model_copy(update={"items": normalized_items})
        validate_quiz_items(
            result.items,
            expected_num_questions=num_questions,
            eligible_profiles=profile_plan["eligible_profiles"],
            expected_profile_counts=adjusted_profile_counts,
        )
        return result

    def generate_study_guide(
        self, lecture: CorpusSelection, chunks: list[ChunkDocument], *, mode: str
    ) -> StudyGuide:
        prompt = self._build_guide_prompt(lecture, chunks, mode)
        guide = self.guide_agent.run_sync(prompt).output
        return self._normalize_study_guide(lecture, chunks, guide)

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
    ) -> EvaluationSummary:
        prompt = (
            f"corpus_id={lecture.corpus_id}\n"
            f"mode={mode}\n"
            f"latency_ms={latency_ms}\n"
            f"token_cost_hint={token_cost_hint}\n"
            f"quiz_set={quiz_set.model_dump_json()}\n"
            f"study_guide={study_guide.model_dump_json()}\n"
        )
        return self.eval_agent.run_sync(prompt).output

    @staticmethod
    def _build_generation_prompt(
        lecture: CorpusSelection,
        chunks: list[ChunkDocument],
        mode: str,
        num_questions: int,
        choice_count: int | None,
        *,
        eligible_profiles: list[str],
        profile_counts: dict[str, int],
        profile_sequence: list[str],
    ) -> str:
        context = "\n\n".join(f"[{chunk.chunk_id}] {chunk.text}" for chunk in chunks[:8])
        return (
            f"corpus_id={lecture.corpus_id}\n"
            f"mode={mode}\n"
            f"subject={lecture.subject}\n"
            f"content={lecture.content}\n"
            f"learning_goal={lecture.learning_goal}\n"
            f"summary={lecture.summary}\n"
            f"num_questions={num_questions}\n"
            f"preferred_choice_count={choice_count if choice_count is not None else 'auto'}\n"
            f"eligible_profiles={','.join(eligible_profiles)}\n"
            f"target_profile_distribution={profile_counts}\n"
            f"target_profile_sequence={profile_sequence}\n"
            "requirements=\n"
            f"- Return exactly {num_questions} quiz items.\n"
            "- Every item must include question_profile and choice_count.\n"
            "- Use only the eligible profiles.\n"
            "- Match the target_profile_distribution exactly.\n"
            "- basic_eval_4 must use 4 options.\n"
            "- review_5 must use 5 options.\n"
            "- retest_5 must use 5 options and focus on confusion, misconception, or distinction.\n"
            "- Every question must be single-answer only.\n"
            "- Do not use wording like '모두 고르시오', '해당하는 것을 모두', or '복수 선택'.\n"
            "- If a retest_5 item cannot be made clearly discriminative, emit review_5 instead.\n"
            "- Do not return an empty items list.\n"
            "- Use only the provided context.\n"
            "- Every evidence_chunk_ids value must reference a chunk id from context.\n"
            "- model_info should include the provider/model name if possible.\n"
            f"context=\n{context}"
        )

    @staticmethod
    def _build_guide_prompt(
        lecture: CorpusSelection, chunks: list[ChunkDocument], mode: str
    ) -> str:
        context = "\n\n".join(
            f"[{chunk.chunk_id}] {chunk.text}" for chunk in chunks[:8]
        )
        return (
            f"corpus_id={lecture.corpus_id}\n"
            f"mode={mode}\n"
            f"subject={lecture.subject}\n"
            f"content={lecture.content}\n"
            f"learning_goal={lecture.learning_goal}\n"
            f"summary={lecture.summary}\n"
            f"context=\n{context}"
        )

    @staticmethod
    def _normalize_study_guide(
        lecture: CorpusSelection,
        chunks: list[ChunkDocument],
        guide: StudyGuide,
    ) -> StudyGuide:
        if guide.summary and guide.key_concepts and guide.review_points:
            return guide

        concepts = extract_concepts(lecture, chunks)
        review_points = [
            chunk.text.split(". ")[0].strip()[:140]
            for chunk in chunks[:5]
            if chunk.text.strip()
        ]
        return guide.model_copy(
            update={
                "summary": guide.summary or lecture.summary,
                "key_concepts": guide.key_concepts or concepts[:5],
                "review_points": guide.review_points or review_points[:5],
                "common_confusions": guide.common_confusions or concepts[:3],
                "recommended_review_order": guide.recommended_review_order or concepts[:5],
                "evidence_chunk_ids": guide.evidence_chunk_ids or [chunk.chunk_id for chunk in chunks[:5]],
            }
        )
