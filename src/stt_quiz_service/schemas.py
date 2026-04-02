from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


MULTI_SELECT_MARKERS = (
    "모두 고르시오",
    "해당하는 것을 모두",
    "복수 선택",
    "다중 선택",
    "모두 선택",
)

ALLOWED_LEARNING_GOAL_ENDINGS = (
    "이해한다",
    "설명할 수 있다",
    "구분할 수 있다",
    "작성할 수 있다",
    "활용할 수 있다",
)


def _corpus_id_from_chunk_id(chunk_id: str) -> str:
    if "-rag-" in chunk_id:
        return chunk_id.split("-rag-", 1)[0]
    return chunk_id.rsplit("-", 1)[0] if "-" in chunk_id else chunk_id


def _stable_weekly_item_id(
    *,
    week_id: str,
    source_corpus_id: str,
    source_date: str,
    topic_axis_label: str,
    question_profile: str,
    question: str,
    options: list[str],
    answer_index: int | None,
    answer_text_open: str | None = None,
) -> str:
    if question_profile == "short_answer":
        payload: dict[str, Any] = {
            "week_id": week_id,
            "source_corpus_id": source_corpus_id,
            "source_date": source_date,
            "topic_axis_label": topic_axis_label,
            "question_profile": question_profile,
            "question": question,
            "answer_text_open": answer_text_open or "",
        }
    else:
        payload = {
            "week_id": week_id,
            "source_corpus_id": source_corpus_id,
            "source_date": source_date,
            "topic_axis_label": topic_axis_label,
            "question_profile": question_profile,
            "question": question,
            "options": options,
            "answer_index": answer_index,
        }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"w{week_id}-{digest}"


class CurriculumRow(BaseModel):
    week: int
    date: str
    session: str
    time: str
    subject: str
    content: str
    learning_goal: str
    instructor: str


class ProcessedLine(BaseModel):
    text: str
    timestamp: str | None = None
    speaker: str | None = None
    practice_example: bool = False
    source_span: str | None = None


class CorpusDocument(BaseModel):
    corpus_id: str
    date: str
    source_path: str
    cleaned_text: str
    summary: str
    lines: list[ProcessedLine] = Field(default_factory=list)


class LectureTargetDocument(BaseModel):
    lecture_id: str
    corpus_id: str
    week: int
    date: str
    session: str
    subject: str
    content: str
    learning_goal: str
    instructor: str
    source_path: str
    summary: str


class ChunkDocument(BaseModel):
    chunk_id: str
    corpus_id: str
    chunk_order: int
    text: str
    source_span: str
    practice_example: bool = False
    metadata: dict[str, str | bool | int] = Field(default_factory=dict)


class DailyTermCandidate(BaseModel):
    term: str
    score: float
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class DailyTermCandidates(BaseModel):
    corpus_id: str
    week_id: str
    candidates: list[DailyTermCandidate]


class TopicAxis(BaseModel):
    label: str
    supporting_terms: list[str]
    evidence_chunk_ids: list[str]
    source_corpus_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_source_corpus_ids(self):
        if self.source_corpus_ids or not self.evidence_chunk_ids:
            return self
        corpus_ids: list[str] = []
        for chunk_id in self.evidence_chunk_ids:
            corpus_id = _corpus_id_from_chunk_id(chunk_id)
            if corpus_id not in corpus_ids:
                corpus_ids.append(corpus_id)
        self.source_corpus_ids = corpus_ids
        return self


class WeeklyTopicSet(BaseModel):
    week_id: str
    topic_axes: list[TopicAxis]
    learning_paragraph: str = ""


class WeeklyGuide(BaseModel):
    week_id: str
    learning_paragraph: str
    topic_axes: list[TopicAxis]
    review_points: list[str] = Field(default_factory=list)
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class QuizItem(BaseModel):
    question_profile: Literal["basic_eval_4", "review_5", "retest_5", "short_answer"]
    choice_count: Literal[4, 5] | None = None
    question: str
    options: list[str] = Field(default_factory=list)
    answer_index: int | None = None
    answer_text: str = ""
    answer_text_open: str | None = None
    scoring_keywords: list[str] = Field(default_factory=list)
    explanation: str
    difficulty: str
    evidence_chunk_ids: list[str]
    learning_goal: str

    @model_validator(mode="after")
    def validate_single_answer_shape(self):
        normalized_question = self.question.replace(" ", "")
        if any(marker.replace(" ", "") in normalized_question for marker in MULTI_SELECT_MARKERS):
            raise ValueError("multi-select wording is not allowed for single-answer quiz items")
        if not self.evidence_chunk_ids:
            raise ValueError("at least one evidence_chunk_id is required")
        if self.question_profile == "short_answer":
            if not self.answer_text_open:
                raise ValueError("short_answer items must have answer_text_open")
            if not self.scoring_keywords:
                raise ValueError("short_answer items must have scoring_keywords")
            return self
        if self.choice_count is None:
            raise ValueError("choice_count is required for multiple-choice items")
        if len(self.options) != self.choice_count:
            raise ValueError("options length must match choice_count")
        if len(set(self.options)) != len(self.options):
            raise ValueError("duplicate options are not allowed")
        if self.answer_index is None or not 0 <= self.answer_index < len(self.options):
            raise ValueError("answer_index must point to a valid option")
        if self.options[self.answer_index].strip() != self.answer_text.strip():
            # LLM이 answer_text와 answer_index를 불일치하게 생성한 경우 자동 보정
            object.__setattr__(self, "answer_text", self.options[self.answer_index])
        return self


class WeeklyQuizItem(QuizItem):
    item_id: str = ""
    topic_axis_label: str
    source_corpus_id: str = ""
    source_date: str = ""
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    learning_goal_source: Literal["metadata", "generated"] = "generated"

    @model_validator(mode="after")
    def validate_source_fields(self):
        if self.source_corpus_id and not self.source_date:
            self.source_date = self.source_corpus_id
        if not self.retrieved_chunk_ids:
            self.retrieved_chunk_ids = list(self.evidence_chunk_ids)
        if not self.learning_goal_source:
            self.learning_goal_source = "generated"
        return self

    def to_learner_item(self) -> "WeeklyQuizLearnerItem":
        return WeeklyQuizLearnerItem(
            item_id=self.item_id,
            question_profile=self.question_profile,
            choice_count=self.choice_count,
            question=self.question,
            options=self.options,
            difficulty=self.difficulty,
            evidence_chunk_ids=self.evidence_chunk_ids,
            learning_goal=self.learning_goal,
            topic_axis_label=self.topic_axis_label,
            source_corpus_id=self.source_corpus_id,
            source_date=self.source_date,
            retrieved_chunk_ids=self.retrieved_chunk_ids,
            learning_goal_source=self.learning_goal_source,
            # short_answer: scoring_keywords 노출, answer_text_open은 노출 안 함
            scoring_keywords=self.scoring_keywords,
        )


class WeeklyQuizBatch(BaseModel):
    items: list[WeeklyQuizItem]


class QuizSet(BaseModel):
    corpus_id: str
    mode: str
    items: list[QuizItem]
    model_info: dict[str, str] = Field(default_factory=dict)
    evaluation_summary: dict[str, float | int | str] = Field(default_factory=dict)


class WeeklyQuizSet(BaseModel):
    week_id: str
    mode: str
    topic_axes: list[TopicAxis]
    items: list[WeeklyQuizItem]
    corpus_ids: list[str] = Field(default_factory=list)
    min_questions_per_corpus: int = Field(default=5, ge=1)
    model_info: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_weekly_corpus_coverage(self):
        if not self.items:
            raise ValueError("weekly quiz set must contain at least one item")
        if not self.corpus_ids:
            self.corpus_ids = sorted({item.source_corpus_id for item in self.items})
        axis_by_label = {axis.label: axis for axis in self.topic_axes}
        for item in self.items:
            if not item.source_corpus_id:
                raise ValueError("weekly quiz items must include source_corpus_id")
            if not item.source_date:
                item.source_date = item.source_corpus_id
            if not item.retrieved_chunk_ids:
                item.retrieved_chunk_ids = list(item.evidence_chunk_ids)
            item.item_id = _stable_weekly_item_id(
                week_id=self.week_id,
                source_corpus_id=item.source_corpus_id,
                source_date=item.source_date,
                topic_axis_label=item.topic_axis_label,
                question_profile=item.question_profile,
                question=item.question,
                options=item.options,
                answer_index=item.answer_index,
                answer_text_open=item.answer_text_open,
            )
            if item.topic_axis_label not in axis_by_label:
                raise ValueError(f"unknown topic_axis_label in weekly quiz item: {item.topic_axis_label}")
            axis = axis_by_label[item.topic_axis_label]
            if item.source_corpus_id not in axis.source_corpus_ids:
                raise ValueError(
                    "weekly quiz item source_corpus_id must be included in the topic axis source_corpus_ids: "
                    f"{item.topic_axis_label} vs {item.source_corpus_id}"
                )
            normalized_learning_goal = item.learning_goal.strip().rstrip(". ")
            if "/" in item.learning_goal:
                raise ValueError("weekly quiz learning_goal must be a single sentence without slash-separated multi-goals")
            if not any(normalized_learning_goal.endswith(ending) for ending in ALLOWED_LEARNING_GOAL_ENDINGS):
                raise ValueError(
                    "weekly quiz learning_goal must end with one of the allowed endings: "
                    f"{ALLOWED_LEARNING_GOAL_ENDINGS}"
                )
        counts = Counter(item.source_corpus_id for item in self.items)
        unknown_corpus_ids = sorted(set(counts) - set(self.corpus_ids))
        if unknown_corpus_ids:
            raise ValueError(f"weekly quiz contains items for unknown corpus_ids: {unknown_corpus_ids}")
        missing = [
            corpus_id
            for corpus_id in self.corpus_ids
            if counts.get(corpus_id, 0) < self.min_questions_per_corpus
        ]
        if missing:
            details = {corpus_id: counts.get(corpus_id, 0) for corpus_id in self.corpus_ids}
            raise ValueError(
                "weekly quiz must contain at least "
                f"{self.min_questions_per_corpus} items per corpus: {details}"
            )
        tuple_counts = Counter(
            (item.source_corpus_id, tuple(item.retrieved_chunk_ids))
            for item in self.items
        )
        overused_tuples = [
            {
                "source_corpus_id": corpus_id,
                "retrieved_chunk_ids": list(chunk_ids),
                "count": count,
            }
            for (corpus_id, chunk_ids), count in tuple_counts.items()
            if count > 2
        ]
        if overused_tuples:
            raise ValueError(
                "weekly quiz retrieved_chunk_ids tuples must not be reused more than twice per corpus: "
                f"{overused_tuples}"
            )
        for item in self.items:
            for chunk_id in item.evidence_chunk_ids:
                if _corpus_id_from_chunk_id(chunk_id) != item.source_corpus_id:
                    raise ValueError(
                        f"weekly quiz item evidence must stay within source_corpus_id: "
                        f"{item.source_corpus_id} vs {chunk_id}"
                    )
            for chunk_id in item.retrieved_chunk_ids:
                if _corpus_id_from_chunk_id(chunk_id) != item.source_corpus_id:
                    raise ValueError(
                        f"weekly quiz item retrieval must stay within source_corpus_id: "
                        f"{item.source_corpus_id} vs {chunk_id}"
                    )
        item_id_counts = Counter(item.item_id for item in self.items)
        duplicate_item_ids = sorted(item_id for item_id, count in item_id_counts.items() if count > 1)
        if duplicate_item_ids:
            raise ValueError(f"weekly quiz contains duplicate item_ids: {duplicate_item_ids}")
        return self

    def to_learner_set(self) -> "WeeklyQuizLearnerSet":
        return WeeklyQuizLearnerSet(
            week_id=self.week_id,
            mode=self.mode,
            topic_axes=self.topic_axes,
            items=[item.to_learner_item() for item in self.items],
            corpus_ids=self.corpus_ids,
            min_questions_per_corpus=self.min_questions_per_corpus,
            model_info=self.model_info,
        )


class WeeklyQuizLearnerItem(BaseModel):
    item_id: str
    question_profile: Literal["basic_eval_4", "review_5", "retest_5", "short_answer"]
    choice_count: Literal[4, 5] | None = None
    question: str
    options: list[str] = Field(default_factory=list)
    difficulty: str
    evidence_chunk_ids: list[str]
    learning_goal: str
    topic_axis_label: str
    source_corpus_id: str
    source_date: str
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    learning_goal_source: Literal["metadata", "generated"] = "generated"
    scoring_keywords: list[str] = Field(default_factory=list)


class WeeklyQuizLearnerSet(BaseModel):
    week_id: str
    mode: str
    topic_axes: list[TopicAxis]
    items: list[WeeklyQuizLearnerItem]
    corpus_ids: list[str] = Field(default_factory=list)
    min_questions_per_corpus: int = Field(default=5, ge=1)
    model_info: dict[str, str] = Field(default_factory=dict)


class WeeklyQuizSubmissionAnswer(BaseModel):
    item_id: str = Field(min_length=1)
    selected_option_index: int | None = Field(default=None, ge=0)
    selected_text: str | None = None

    @field_validator("item_id")
    @classmethod
    def normalize_item_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("item_id is required")
        return normalized

    @model_validator(mode="after")
    def validate_answer_provided(self):
        if self.selected_option_index is None and self.selected_text is None:
            raise ValueError("either selected_option_index or selected_text must be provided")
        return self


class WeeklyQuizSubmissionRequest(BaseModel):
    answers: list[WeeklyQuizSubmissionAnswer] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_item_ids(self):
        counts = Counter(answer.item_id for answer in self.answers)
        duplicate_item_ids = sorted(item_id for item_id, count in counts.items() if count > 1)
        if duplicate_item_ids:
            raise ValueError(f"duplicate item_id answers are not allowed: {duplicate_item_ids}")
        return self


class WeeklyQuizSubmissionResult(BaseModel):
    item_id: str
    selected_option_index: int | None = None
    selected_text: str | None = None
    correct_option_index: int | None = None
    answer_text: str = ""
    answer_text_open: str | None = None
    explanation: str
    is_correct: bool


class WeeklyQuizSubmissionResponse(BaseModel):
    attempt_id: str
    week_id: str
    submitted_at: str
    total_questions: int
    correct_count: int
    score: int
    results: list[WeeklyQuizSubmissionResult]
    learner_memo: WeeklyLearnerMemo | None = None


class WeeklyQuizReviewResult(BaseModel):
    item_id: str
    question: str
    options: list[str] = Field(default_factory=list)
    selected_option_index: int | None = None
    selected_text: str | None = None
    correct_option_index: int | None = None
    answer_text: str = ""
    answer_text_open: str | None = None
    explanation: str
    is_correct: bool
    topic_axis_label: str
    source_corpus_id: str
    source_date: str
    learning_goal: str
    learning_goal_source: Literal["metadata", "generated"] = "generated"
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class WeeklyQuizSubmissionDetailResponse(BaseModel):
    attempt_id: str
    week_id: str
    total_questions: int
    correct_count: int
    score: int
    submitted_at: str
    results: list[WeeklyQuizReviewResult]


class WeeklyQuestionTypeMetric(BaseModel):
    question_profile: str
    question_count: int
    covered_topic_axes: list[str] = Field(default_factory=list)


class WeeklyTopicCoverage(BaseModel):
    topic_axis_label: str
    question_count: int
    supporting_terms: list[str] = Field(default_factory=list)


class WeeklyReport(BaseModel):
    week_id: str
    question_type_metrics: list[WeeklyQuestionTypeMetric]
    topic_coverage: list[WeeklyTopicCoverage]
    mismatched_axis_item_count: int = 0
    learning_goal_source_distribution: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class WeeklyLearnerMemoFocusTopic(BaseModel):
    label: str
    wrong_count: int = Field(ge=1)


class WeeklyLearnerMemoFocusDate(BaseModel):
    source_date: str
    wrong_count: int = Field(ge=1)


class WeeklyLearnerMemoWeekAxis(BaseModel):
    label: str
    supporting_terms: list[str] = Field(default_factory=list)


class WeeklyLearnerMemoWeekContext(BaseModel):
    week_id: str
    dates: list[str] = Field(default_factory=list)
    topic_axes: list[WeeklyLearnerMemoWeekAxis] = Field(default_factory=list)
    learning_paragraph: str
    review_points: list[str] = Field(default_factory=list)


class WeeklyLearnerMemoSubmissionSummary(BaseModel):
    total_questions: int
    correct_count: int
    wrong_count: int
    score: int
    wrong_count_by_topic_axis: list[WeeklyLearnerMemoFocusTopic] = Field(default_factory=list)
    wrong_count_by_source_date: list[WeeklyLearnerMemoFocusDate] = Field(default_factory=list)
    wrong_count_by_question_profile: dict[str, int] = Field(default_factory=dict)


class WeeklyLearnerMemoWrongExample(BaseModel):
    question: str
    selected_answer_text: str
    correct_answer_text: str
    explanation: str
    topic_axis_label: str
    source_date: str


class WeeklyLearnerMemoInput(BaseModel):
    week_context: WeeklyLearnerMemoWeekContext
    submission_summary: WeeklyLearnerMemoSubmissionSummary
    representative_wrong_examples: list[WeeklyLearnerMemoWrongExample] = Field(default_factory=list)
    recommended_review_candidates: list[str] = Field(default_factory=list)


class WeeklyLearnerMemo(BaseModel):
    status: Literal["no_submission", "all_correct", "ready"]
    headline: str
    summary: str
    recommended_review_points: list[str] = Field(default_factory=list)
    focus_topics: list[WeeklyLearnerMemoFocusTopic] = Field(default_factory=list)
    focus_dates: list[WeeklyLearnerMemoFocusDate] = Field(default_factory=list)


class WeeklyReportResponse(WeeklyReport):
    learner_memo: WeeklyLearnerMemo


class StudyGuide(BaseModel):
    corpus_id: str
    summary: str
    key_concepts: list[str]
    review_points: list[str]
    common_confusions: list[str]
    recommended_review_order: list[str]
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class EvaluationIssue(BaseModel):
    code: str
    message: str


class EvaluationSummary(BaseModel):
    corpus_id: str
    mode: str
    faithfulness_score: float
    clarity_score: float
    duplication_score: float
    coverage_score: float
    latency_ms: int
    token_cost_hint: float
    issues: list[EvaluationIssue] = Field(default_factory=list)


class RetrievalHit(BaseModel):
    chunk_id: str
    corpus_id: str
    chunk_order: int
    text: str
    source_span: str
    practice_example: bool = False
    metadata: dict[str, str | bool | int] = Field(default_factory=dict)
    rank: int
    score: float

    def to_chunk_document(self) -> "ChunkDocument":
        return ChunkDocument(
            chunk_id=self.chunk_id,
            corpus_id=self.corpus_id,
            chunk_order=self.chunk_order,
            text=self.text,
            source_span=self.source_span,
            practice_example=self.practice_example,
            metadata=self.metadata,
        )


class RunLog(BaseModel):
    run_id: str
    corpus_id: str
    mode: str
    retrieval_query: str = ""
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    retrieval_hits: list[RetrievalHit] = Field(default_factory=list)
    retrieval_top_k: int = 0
    embedder_provider: str = ""
    profile_distribution: dict[str, int] = Field(default_factory=dict)
    latency_ms: int = 0
    token_usage: int = 0
    model_name: str = ""
    evaluation: EvaluationSummary | None = None


class AuditEvent(BaseModel):
    event_id: str
    created_at: str
    actor: str
    event_type: str
    status: str
    lecture_id: str | None = None
    run_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    transcripts_root: str
    curriculum_path: str


class IngestResponse(BaseModel):
    lectures_ingested: int
    chunks_ingested: int
    target_ids: list[str]


class PrepareResponse(BaseModel):
    corpus_version: str
    corpora_prepared: int
    targets_prepared: int
    chunks_prepared: int
    corpus_ids: list[str]
    target_ids: list[str]
    output_dir: str
    skipped: bool = False


class IndexResponse(BaseModel):
    corpus_version: str
    corpora_indexed: int
    chunks_indexed: int
    embedder_provider: str
    dimension: int
    skipped: bool = False


class PipelinePrepareRequest(BaseModel):
    transcripts_root: str
    curriculum_path: str
    output_dir: str = "artifacts/preprocessed"
    persist_to_db: bool = True
    preprocess_model_override: str | None = None


class PipelineIndexRequest(BaseModel):
    corpus_ids: list[str] | None = None


class PipelineGenerateRequest(BaseModel):
    corpus_ids: list[str] | None = None
    mode: str = "rag"
    num_questions: int = Field(default=5, ge=5)
    choice_count: Literal[4, 5] | None = None


class PipelineExtractTermCandidatesRequest(BaseModel):
    corpus_ids: list[str] | None = None


class PipelineExtractTermCandidatesResponse(BaseModel):
    corpus_ids: list[str]
    extracted_count: int


class PipelineBuildWeeklyTopicsRequest(BaseModel):
    week_ids: list[str] | None = None


class PipelineBuildWeeklyTopicsResponse(BaseModel):
    week_ids: list[str]
    built_count: int


class PipelineGenerateWeeklyGuidesRequest(BaseModel):
    week_ids: list[str] | None = None


class PipelineGenerateWeeklyGuidesResponse(BaseModel):
    week_ids: list[str]
    generated_count: int


class PipelineGenerateWeeklyQuizzesRequest(BaseModel):
    week_ids: list[str] | None = None
    mode: str = "weekly"
    num_questions: int = Field(default=5, ge=5)


class PipelineGenerateWeeklyQuizzesResponse(BaseModel):
    week_ids: list[str]
    generated_count: int


class WeeklySelection(BaseModel):
    week_id: str
    week: int
    corpus_ids: list[str]
    dates: list[str]
    subject: str
    content: str
    learning_goal: str


class StoredBundleResponse(BaseModel):
    run: RunLog
    quiz_set: QuizSet
    study_guide: StudyGuide


class GenerateQuizRequest(BaseModel):
    corpus_id: str
    mode: str = "rag"
    num_questions: int = Field(default=5, ge=5)
    choice_count: Literal[4, 5] | None = None


class GenerateGuideRequest(BaseModel):
    corpus_id: str
    mode: str = "rag"


class GenerateBundleRequest(BaseModel):
    corpus_id: str
    mode: str = "rag"
    num_questions: int = Field(default=5, ge=5)
    choice_count: Literal[4, 5] | None = None


class BundleResponse(BaseModel):
    run: RunLog
    quiz_set: QuizSet
    study_guide: StudyGuide


class WeeklyBundleResponse(BaseModel):
    topics: WeeklyTopicSet
    guide: WeeklyGuide
    quiz_set: WeeklyQuizLearnerSet
    report: WeeklyReport


class ConceptTerm(BaseModel):
    term: str
    score: float
    rank: int


class WeeklyConceptMapResponse(BaseModel):
    week_id: str
    terms: list[ConceptTerm]
    max_score: float
    min_score: float
