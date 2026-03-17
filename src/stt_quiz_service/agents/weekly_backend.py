from __future__ import annotations

from collections import defaultdict

from pydantic_ai import Agent

from stt_quiz_service.agents.base import WeeklyGenerationBackend
from stt_quiz_service.config import Settings
from stt_quiz_service.prompts import read_prompt_section
from stt_quiz_service.schemas import (
    ChunkDocument,
    DailyTermCandidates,
    TopicAxis,
    WeeklyGuide,
    WeeklyQuizItem,
    WeeklyQuizSet,
    WeeklySelection,
    WeeklyTopicSet,
)


PROFILE_SEQUENCE = ["basic_eval_4", "review_5", "basic_eval_4", "review_5", "retest_5"]
PROFILE_CHOICE_COUNT = {
    "basic_eval_4": 4,
    "review_5": 5,
    "retest_5": 5,
}


def _serialize_candidates(candidate_terms: list[DailyTermCandidates]) -> str:
    sections: list[str] = []
    for candidate_set in candidate_terms:
        terms = ", ".join(
            f"{candidate.term}({candidate.score:.3f})"
            for candidate in candidate_set.candidates[:20]
        )
        sections.append(f"{candidate_set.corpus_id}: {terms}")
    return "\n".join(sections)


def _serialize_chunks(chunks: list[ChunkDocument], *, limit: int = 12) -> str:
    return "\n\n".join(f"[{chunk.chunk_id}] {chunk.text}" for chunk in chunks[:limit])


class MockWeeklyGenerationBackend(WeeklyGenerationBackend):
    model_name = "mock-weekly-rules"

    def build_weekly_topic_set(
        self,
        week: WeeklySelection,
        candidate_terms: list[DailyTermCandidates],
        chunks: list[ChunkDocument],
    ) -> WeeklyTopicSet:
        merged: list[tuple[str, float, list[str], list[str]]] = []
        seen: set[str] = set()
        for candidate_set in candidate_terms:
            for candidate in candidate_set.candidates:
                key = candidate.term.casefold()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(
                    (
                        candidate.term,
                        candidate.score,
                        candidate.evidence_chunk_ids,
                        [candidate_set.corpus_id],
                    )
                )
        merged.sort(key=lambda item: (-item[1], item[0]))
        axes: list[TopicAxis] = []
        for term, _score, evidence_chunk_ids, source_corpus_ids in merged[:3]:
            supporting_terms = [term]
            for other_term, _, _, _ in merged:
                if other_term == term or len(supporting_terms) >= 4:
                    continue
                supporting_terms.append(other_term)
            axes.append(
                TopicAxis(
                    label=term,
                    supporting_terms=supporting_terms[:4],
                    evidence_chunk_ids=evidence_chunk_ids[:3] or [chunk.chunk_id for chunk in chunks[:2]],
                    source_corpus_ids=[],
                )
            )
        return WeeklyTopicSet(week_id=week.week_id, topic_axes=axes[:3], learning_paragraph="")

    def generate_weekly_guide(
        self,
        week: WeeklySelection,
        topic_set: WeeklyTopicSet,
        chunks: list[ChunkDocument],
    ) -> WeeklyGuide:
        topic_names = ", ".join(axis.label for axis in topic_set.topic_axes)
        paragraph = (
            f"{week.week_id}주차 강의는 {topic_names}를 중심으로 진행됩니다. "
            f"각 주제는 실제 코드와 개념 설명이 함께 등장하므로 supporting terms를 같이 복습하는 것이 중요합니다. "
            f"특히 강의 예시가 어떻게 핵심 개념으로 연결되는지 확인하면서 읽으면 이해가 빨라집니다."
        )
        return WeeklyGuide(
            week_id=week.week_id,
            learning_paragraph=paragraph,
            topic_axes=topic_set.topic_axes,
            review_points=[axis.label for axis in topic_set.topic_axes],
            evidence_chunk_ids=list(
                dict.fromkeys(chunk_id for axis in topic_set.topic_axes for chunk_id in axis.evidence_chunk_ids)
            )[:8],
        )

    def generate_weekly_quiz_set(
        self,
        week: WeeklySelection,
        topic_set: WeeklyTopicSet,
        chunks: list[ChunkDocument],
        *,
        num_questions: int,
    ) -> WeeklyQuizSet:
        items: list[WeeklyQuizItem] = []
        fallback_distractors = [
            "강의와 무관한 외부 개념만 설명한다.",
            "핵심 개념의 정의 없이 단편적인 사례만 나열한다.",
            "해당 주차 학습 목표와 직접 연결되지 않는다.",
            "강의에서 구분한 개념 차이를 무시한다.",
        ]
        axes = topic_set.topic_axes or [
            TopicAxis(label="핵심 주제", supporting_terms=["핵심 주제"], evidence_chunk_ids=[], source_corpus_ids=[])
        ]
        quiz_axes = list(axes)
        for corpus_id in week.corpus_ids:
            if any(corpus_id in axis.source_corpus_ids for axis in quiz_axes):
                continue
            fallback_evidence = [chunk.chunk_id for chunk in chunks if chunk.corpus_id == corpus_id][:2]
            quiz_axes.append(
                TopicAxis(
                    label=f"{corpus_id} 핵심 주제",
                    supporting_terms=[f"{corpus_id} 핵심 주제"],
                    evidence_chunk_ids=fallback_evidence,
                    source_corpus_ids=[corpus_id],
                )
            )
        for corpus_index, corpus_id in enumerate(week.corpus_ids):
            corpus_axes = [axis for axis in quiz_axes if corpus_id in axis.source_corpus_ids] or quiz_axes
            source_date = corpus_id
            corpus_chunk_ids = [chunk.chunk_id for chunk in chunks if chunk.corpus_id == corpus_id]
            for index in range(num_questions):
                axis = corpus_axes[index % len(corpus_axes)]
                profile = PROFILE_SEQUENCE[index % len(PROFILE_SEQUENCE)]
                choice_count = PROFILE_CHOICE_COUNT[profile]
                correct = (
                    f"`{axis.label}`은/는 {', '.join(axis.supporting_terms[:2])}와 연결되는 주차 핵심 주제이다."
                    if profile != "retest_5"
                    else f"`{axis.label}`은/는 supporting terms와 무관하다고 설명되었다."
                )
                options = fallback_distractors[: choice_count - 1]
                answer_index = index % choice_count
                options.insert(answer_index, correct)
                evidence_chunk_ids = [
                    chunk_id
                    for chunk_id in axis.evidence_chunk_ids
                    if chunk_id.startswith(corpus_id)
                ][:2]
                if not evidence_chunk_ids:
                    if corpus_chunk_ids:
                        start = index % len(corpus_chunk_ids)
                        window = corpus_chunk_ids[start : start + 2]
                        if len(window) < 2:
                            window += corpus_chunk_ids[: 2 - len(window)]
                        evidence_chunk_ids = window[:2]
                    else:
                        evidence_chunk_ids = []
                elif corpus_chunk_ids:
                    start = index % len(corpus_chunk_ids)
                    window = corpus_chunk_ids[start : start + len(evidence_chunk_ids)]
                    if len(window) < len(evidence_chunk_ids):
                        window += corpus_chunk_ids[: len(evidence_chunk_ids) - len(window)]
                    evidence_chunk_ids = window[: len(evidence_chunk_ids)]
                items.append(
                    WeeklyQuizItem(
                        topic_axis_label=axis.label,
                        question_profile=profile,
                        choice_count=choice_count,
                        question=self._question_text(axis.label, profile),
                        options=options,
                        answer_index=answer_index,
                        answer_text=correct,
                        explanation=f"`{axis.label}` 관련 supporting terms와 evidence chunk를 기준으로 판단해야 한다.",
                        difficulty={"basic_eval_4": "easy", "review_5": "medium", "retest_5": "hard"}[profile],
                        evidence_chunk_ids=evidence_chunk_ids,
                        learning_goal="핵심 개념을 설명할 수 있다.",
                        source_corpus_id=corpus_id,
                        source_date=source_date,
                        retrieved_chunk_ids=evidence_chunk_ids,
                        learning_goal_source="generated",
                    )
                )
        return WeeklyQuizSet(
            week_id=week.week_id,
            mode="weekly",
            topic_axes=quiz_axes,
            items=items,
            corpus_ids=week.corpus_ids,
            min_questions_per_corpus=num_questions,
            model_info={"backend": self.model_name},
        )

    @staticmethod
    def _question_text(label: str, profile: str) -> str:
        if profile == "basic_eval_4":
            return f"다음 중 `{label}`에 대한 weekly 핵심 설명으로 가장 적절한 것은 무엇인가?"
        if profile == "review_5":
            return f"`{label}`과 관련된 supporting terms를 가장 잘 연결한 설명은 무엇인가?"
        return f"다음 중 `{label}`에 대한 설명으로 옳지 않은 것을 고르시오."


class PydanticAIWeeklyGenerationBackend(WeeklyGenerationBackend):
    def __init__(self, settings: Settings):
        self.model_name = settings.weekly_model
        self.topic_agent = Agent(
            self.model_name,
            output_type=WeeklyTopicSet,
            system_prompt=read_prompt_section("Weekly Topic Consolidation System Prompt"),
        )
        self.guide_agent = Agent(
            self.model_name,
            output_type=WeeklyGuide,
            system_prompt=read_prompt_section("Weekly Guide Generation System Prompt"),
        )
        self.quiz_agent = Agent(
            self.model_name,
            output_type=WeeklyQuizSet,
            system_prompt=read_prompt_section("Weekly Quiz Generation System Prompt"),
        )

    def build_weekly_topic_set(
        self,
        week: WeeklySelection,
        candidate_terms: list[DailyTermCandidates],
        chunks: list[ChunkDocument],
    ) -> WeeklyTopicSet:
        prompt = (
            f"week_id={week.week_id}\n"
            f"dates={week.dates}\n"
            f"subject={week.subject}\n"
            f"content={week.content}\n"
            f"learning_goal={week.learning_goal}\n"
            f"candidate_terms=\n{_serialize_candidates(candidate_terms)}\n\n"
            f"evidence_chunks=\n{_serialize_chunks(chunks)}"
        )
        topic_set = self.topic_agent.run_sync(prompt).output
        return topic_set.model_copy(update={"week_id": week.week_id})

    def generate_weekly_guide(
        self,
        week: WeeklySelection,
        topic_set: WeeklyTopicSet,
        chunks: list[ChunkDocument],
    ) -> WeeklyGuide:
        prompt = (
            f"week_id={week.week_id}\n"
            f"dates={week.dates}\n"
            f"topic_axes={topic_set.model_dump_json()}\n"
            f"evidence_chunks=\n{_serialize_chunks(chunks)}"
        )
        guide = self.guide_agent.run_sync(prompt).output
        topic_evidence = list(
            dict.fromkeys(
                chunk_id
                for axis in topic_set.topic_axes
                for chunk_id in axis.evidence_chunk_ids
            )
        )
        return guide.model_copy(
            update={
                "week_id": week.week_id,
                "topic_axes": topic_set.topic_axes,
                "evidence_chunk_ids": guide.evidence_chunk_ids or topic_evidence,
            }
        )

    def generate_weekly_quiz_set(
        self,
        week: WeeklySelection,
        topic_set: WeeklyTopicSet,
        chunks: list[ChunkDocument],
        *,
        num_questions: int,
    ) -> WeeklyQuizSet:
        grouped_chunks: dict[str, list[ChunkDocument]] = defaultdict(list)
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        for axis in topic_set.topic_axes:
            for chunk_id in axis.evidence_chunk_ids:
                chunk = chunk_by_id.get(chunk_id)
                if chunk:
                    grouped_chunks[axis.label].append(chunk)
        axis_context_parts: list[str] = []
        for axis in topic_set.topic_axes:
            axis_chunks = grouped_chunks.get(axis.label, [])[:3]
            axis_context_parts.append(
                f"[axis={axis.label}] supporting_terms={axis.supporting_terms}\n{_serialize_chunks(axis_chunks, limit=3)}"
            )
        prompt = (
            f"week_id={week.week_id}\n"
            f"num_questions={num_questions}\n"
            f"topic_axes={topic_set.model_dump_json()}\n"
            f"axis_context=\n{'\n\n'.join(axis_context_parts)}"
        )
        quiz_set = self.quiz_agent.run_sync(prompt).output
        return quiz_set.model_copy(update={"week_id": week.week_id, "topic_axes": topic_set.topic_axes})
