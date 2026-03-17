from __future__ import annotations

from collections import Counter
import re

from stt_quiz_service.agents.base import GenerationBackend
from stt_quiz_service.schemas import (
    ChunkDocument,
    EvaluationIssue,
    EvaluationSummary,
    QuizItem,
    QuizSet,
    StudyGuide,
)
from stt_quiz_service.storage.repository import CorpusSelection
from stt_quiz_service.services.retrieval import extract_concepts
from stt_quiz_service.services.quiz_profiles import (
    PROFILE_CHOICE_COUNT,
    build_profile_plan,
    is_discriminative_retest_item,
    summarize_profile_distribution,
    validate_quiz_items,
)


TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣_]{2,}")


class MockGenerationBackend(GenerationBackend):
    model_name = "mock-rules"

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
        concepts = profile_plan["concepts"]
        if not concepts:
            concepts = ["핵심 개념"]
        items: list[QuizItem] = []
        fallback_distractors = [
            "강의에서 다루지 않은 외부 사례만 설명한다.",
            "학습목표와 무관한 운영 절차만 강조한다.",
            "정의 없이 결과 암기만 요구한다.",
            "단일 예시만 외우도록 구성한다.",
            "비슷해 보이지만 강의 맥락과는 다른 설명이다.",
        ]
        for index, profile in enumerate(profile_plan["profile_sequence"]):
            concept = concepts[index % len(concepts)]
            chunk = chunks[index % len(chunks)] if chunks else ChunkDocument(
                chunk_id="fallback",
                corpus_id=lecture.corpus_id,
                chunk_order=0,
                text=lecture.summary,
                source_span="0:0",
                practice_example=False,
                metadata={},
            )
            current_choice_count = PROFILE_CHOICE_COUNT[profile]
            correct, options, answer_index = self._build_options(
                lecture=lecture,
                chunk=chunk,
                concept=concept,
                profile=profile,
                choice_count=current_choice_count,
                fallback_distractors=fallback_distractors,
                answer_index=index % current_choice_count,
            )
            item = QuizItem(
                question_profile=profile,
                choice_count=current_choice_count,
                question=self._build_question_text(concept, profile),
                options=options,
                answer_index=answer_index,
                answer_text=correct,
                explanation=self._build_explanation(concept, correct, profile),
                difficulty=self._difficulty_for_profile(profile),
                evidence_chunk_ids=[chunk.chunk_id],
                learning_goal=lecture.learning_goal,
            )
            items.append(item)
        validate_quiz_items(
            items,
            expected_num_questions=num_questions,
            eligible_profiles=profile_plan["eligible_profiles"],
            expected_profile_counts=profile_plan["profile_counts"],
        )
        return QuizSet(
            corpus_id=lecture.corpus_id,
            mode=mode,
            items=items,
            model_info={
                "backend": self.model_name,
                "eligible_profiles": ",".join(profile_plan["eligible_profiles"]),
            },
        )

    def generate_study_guide(
        self, lecture: CorpusSelection, chunks: list[ChunkDocument], *, mode: str
    ) -> StudyGuide:
        concepts = extract_concepts(lecture, chunks)
        chunk_summaries = [self._first_sentence(chunk.text) for chunk in chunks[:5]]
        confusion_candidates = self._common_terms(chunks)
        return StudyGuide(
            corpus_id=lecture.corpus_id,
            summary=lecture.summary,
            key_concepts=concepts[:6],
            review_points=chunk_summaries[:5],
            common_confusions=confusion_candidates[:3]
            or ["용어 구분", "핵심 개념의 적용 맥락"],
            recommended_review_order=concepts[:6],
            evidence_chunk_ids=[chunk.chunk_id for chunk in chunks[:5]],
        )

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
        issues: list[EvaluationIssue] = []
        duplicate_questions = len({item.question for item in quiz_set.items}) != len(quiz_set.items)
        if duplicate_questions:
            issues.append(EvaluationIssue(code="duplicate_question", message="중복 문항이 감지되었습니다."))
        for item in quiz_set.items:
            if not (0 <= item.answer_index < len(item.options)):
                issues.append(EvaluationIssue(code="invalid_answer_index", message="정답 인덱스가 보기 범위를 벗어났습니다."))
            if len(set(item.options)) != len(item.options):
                issues.append(EvaluationIssue(code="duplicate_option", message="중복 보기 항목이 있습니다."))
            if not item.evidence_chunk_ids:
                issues.append(EvaluationIssue(code="missing_evidence", message="근거 청크가 비어 있습니다."))
            expected_choice_count = PROFILE_CHOICE_COUNT[item.question_profile]
            if item.choice_count != expected_choice_count or len(item.options) != expected_choice_count:
                issues.append(EvaluationIssue(code="invalid_choice_count", message="문항 프로필과 보기 수가 일치하지 않습니다."))
            if item.question_profile == "retest_5" and not is_discriminative_retest_item(item):
                issues.append(EvaluationIssue(code="weak_retest_item", message="재평가형 문항의 분별력이 약합니다."))
        faithfulness = 1.0 if all(item.evidence_chunk_ids for item in quiz_set.items) else 0.5
        clarity = 1.0 if all(len(set(item.options)) == len(item.options) for item in quiz_set.items) else 0.5
        duplication = 1.0 if not duplicate_questions else 0.4
        coverage = min(1.0, len(study_guide.key_concepts) / 5.0)
        profile_distribution = summarize_profile_distribution(quiz_set.items)
        if len(profile_distribution) < min(2, len(quiz_set.items)):
            issues.append(EvaluationIssue(code="low_profile_variety", message="문항 프로필 다양성이 부족합니다."))
        return EvaluationSummary(
            corpus_id=lecture.corpus_id,
            mode=mode,
            faithfulness_score=faithfulness,
            clarity_score=clarity,
            duplication_score=duplication,
            coverage_score=coverage,
            latency_ms=latency_ms,
            token_cost_hint=token_cost_hint,
            issues=issues,
        )

    @staticmethod
    def _first_sentence(text: str) -> str:
        for separator in [". ", "? ", "! ", "\n"]:
            if separator in text:
                return text.split(separator)[0].strip()
        return text[:140].strip()

    def _summarize_chunk(self, text: str, concept: str) -> str:
        sentence = self._first_sentence(text)
        if concept in sentence:
            return sentence
        return f"`{concept}`은/는 {sentence[:120]}"

    def _common_terms(self, chunks: list[ChunkDocument]) -> list[str]:
        counter: Counter[str] = Counter()
        for chunk in chunks[:8]:
            counter.update(TOKEN_RE.findall(chunk.text))
        return [token for token, _ in counter.most_common(5)]

    def _build_options(
        self,
        *,
        lecture: CorpusSelection,
        chunk: ChunkDocument,
        concept: str,
        profile: str,
        choice_count: int,
        fallback_distractors: list[str],
        answer_index: int,
    ) -> tuple[str, list[str], int]:
        if profile != "retest_5":
            correct = self._summarize_chunk(chunk.text, concept)
            options = fallback_distractors[: choice_count - 1]
            options.insert(answer_index, correct)
            return correct, options, answer_index

        true_base = self._first_sentence(chunk.text)
        true_options = [
            true_base,
            f"`{concept}`은 학습목표와 직접 연결된다.",
            f"`{concept}`은 강의 핵심 복습 포인트에 포함된다.",
            f"`{concept}`은 관련 개념과 구분해서 이해해야 한다.",
        ][: choice_count - 1]
        wrong_option = f"`{concept}`은 강의에서 다른 개념과 차이가 없다고 설명되었다."
        options = list(true_options)
        options.insert(answer_index, wrong_option)
        while len(options) < choice_count:
            options.append(f"`{concept}`에 대한 추가 핵심 설명이다.")
        return wrong_option, options, answer_index

    @staticmethod
    def _build_question_text(concept: str, profile: str) -> str:
        if profile == "basic_eval_4":
            return f"다음 중 `{concept}`에 대해 강의에서 설명한 기본 개념으로 가장 적절한 것은 무엇인가?"
        if profile == "review_5":
            return f"`{concept}`과 관련하여 강의 내용을 가장 잘 요약한 선택지는 무엇인가?"
        return f"다음 중 `{concept}`에 대한 설명으로 옳지 않은 것을 고르시오."

    @staticmethod
    def _build_explanation(concept: str, correct: str, profile: str) -> str:
        if profile == "retest_5":
            return (
                f"`{concept}`은 강의에서 다른 개념과 혼동하기 쉬운 포인트로 설명되었다. "
                f"정답은 그 혼동을 구분하는 근거를 따른다."
            )
        return f"근거 청크에 따르면 `{concept}`은 {correct}"

    @staticmethod
    def _difficulty_for_profile(profile: str) -> str:
        return {
            "basic_eval_4": "easy",
            "review_5": "medium",
            "retest_5": "hard",
        }[profile]
