from __future__ import annotations

from collections import Counter
import json
from typing import Protocol

from pydantic_ai import Agent

from stt_quiz_service.config import Settings
from stt_quiz_service.prompts import read_prompt_section
from stt_quiz_service.schemas import (
    WeeklyGuide,
    WeeklyLearnerMemo,
    WeeklyLearnerMemoFocusDate,
    WeeklyLearnerMemoFocusTopic,
    WeeklyLearnerMemoInput,
    WeeklyLearnerMemoSubmissionSummary,
    WeeklyLearnerMemoWeekAxis,
    WeeklyLearnerMemoWeekContext,
    WeeklyLearnerMemoWrongExample,
    WeeklyQuizReviewResult,
    WeeklyQuizSet,
    WeeklyQuizSubmissionDetailResponse,
    WeeklySelection,
    WeeklyTopicSet,
)


class WeeklyLearnerMemoGenerator(Protocol):
    model_name: str

    def generate(self, context: WeeklyLearnerMemoInput) -> WeeklyLearnerMemo: ...


class MockWeeklyLearnerMemoGenerator:
    model_name = "mock-weekly-learner-memo"

    def generate(self, context: WeeklyLearnerMemoInput) -> WeeklyLearnerMemo:
        focus_topics = context.submission_summary.wrong_count_by_topic_axis[:3]
        focus_dates = context.submission_summary.wrong_count_by_source_date[:3]
        top_topic = focus_topics[0].label if focus_topics else "이번 주 핵심 개념"
        top_date = focus_dates[0].source_date if focus_dates else (
            context.week_context.dates[0] if context.week_context.dates else "이번 주"
        )
        wrong_count = context.submission_summary.wrong_count
        return WeeklyLearnerMemo(
            status="ready",
            headline=f"이번 제출에서는 {top_topic} 관련 오답이 가장 많이 나왔습니다.",
            summary=(
                f"총 {wrong_count}문항을 틀렸고, 특히 {top_date} 강의와 연결된 개념을 다시 점검할 필요가 있습니다."
            ),
            recommended_review_points=context.recommended_review_candidates[:3],
            focus_topics=focus_topics,
            focus_dates=focus_dates,
        )


class PydanticAIWeeklyLearnerMemoGenerator:
    def __init__(self, settings: Settings):
        self.model_name = settings.weekly_model
        shared = read_prompt_section("Shared Rules")
        memo_prompt = f"{shared}\n\n{read_prompt_section('Weekly Learner Memo System Prompt')}"
        self.agent = Agent(
            self.model_name,
            output_type=WeeklyLearnerMemo,
            system_prompt=memo_prompt,
        )

    def generate(self, context: WeeklyLearnerMemoInput) -> WeeklyLearnerMemo:
        prompt = json.dumps(context.model_dump(), ensure_ascii=False, indent=2)
        return self.agent.run_sync(prompt).output


def generate_weekly_learner_memo(
    *,
    week: WeeklySelection,
    topic_set: WeeklyTopicSet,
    guide: WeeklyGuide,
    quiz_set: WeeklyQuizSet,
    latest_submission: WeeklyQuizSubmissionDetailResponse | None,
    generator: WeeklyLearnerMemoGenerator,
) -> WeeklyLearnerMemo:
    base_review_points = _base_review_points(guide, topic_set)
    if latest_submission is None:
        return WeeklyLearnerMemo(
            status="no_submission",
            headline="아직 이번 주 퀴즈 제출 이력이 없습니다.",
            summary="퀴즈를 전부 제출하면 최근 제출 기준의 오답 패턴과 복습 메모를 여기서 안내합니다.",
            recommended_review_points=base_review_points[:3],
            focus_topics=[],
            focus_dates=[],
        )

    wrong_results = [result for result in latest_submission.results if not result.is_correct]
    if not wrong_results:
        return WeeklyLearnerMemo(
            status="all_correct",
            headline="이번 제출은 전 문항 정답입니다.",
            summary="뚜렷한 오답 집중 구간은 없습니다. 아래 복습 포인트만 짧게 점검하면 충분합니다.",
            recommended_review_points=base_review_points[:3],
            focus_topics=[],
            focus_dates=[],
        )

    context = build_weekly_learner_memo_context(
        week=week,
        topic_set=topic_set,
        guide=guide,
        quiz_set=quiz_set,
        latest_submission=latest_submission,
    )
    try:
        memo = generator.generate(context)
    except Exception:
        memo = MockWeeklyLearnerMemoGenerator().generate(context)
    return _normalize_ready_memo(memo, context)


def build_weekly_learner_memo_context(
    *,
    week: WeeklySelection,
    topic_set: WeeklyTopicSet,
    guide: WeeklyGuide,
    quiz_set: WeeklyQuizSet,
    latest_submission: WeeklyQuizSubmissionDetailResponse,
) -> WeeklyLearnerMemoInput:
    item_by_id = {item.item_id: item for item in quiz_set.items}
    wrong_results = [result for result in latest_submission.results if not result.is_correct]
    wrong_count_by_topic_axis = _sorted_topic_focuses(Counter(result.topic_axis_label for result in wrong_results))
    wrong_count_by_source_date = _sorted_date_focuses(Counter(result.source_date for result in wrong_results))
    wrong_count_by_question_profile_counter = Counter(
        item_by_id[result.item_id].question_profile
        for result in wrong_results
        if result.item_id in item_by_id
    )
    wrong_count_by_question_profile = {
        profile: count
        for profile, count in sorted(
            wrong_count_by_question_profile_counter.items(),
            key=lambda item: (-item[1], item[0]),
        )
    }

    return WeeklyLearnerMemoInput(
        week_context=WeeklyLearnerMemoWeekContext(
            week_id=week.week_id,
            dates=week.dates,
            topic_axes=[
                WeeklyLearnerMemoWeekAxis(label=axis.label, supporting_terms=axis.supporting_terms)
                for axis in topic_set.topic_axes
            ],
            learning_paragraph=guide.learning_paragraph,
            review_points=guide.review_points,
        ),
        submission_summary=WeeklyLearnerMemoSubmissionSummary(
            total_questions=latest_submission.total_questions,
            correct_count=latest_submission.correct_count,
            wrong_count=len(wrong_results),
            score=latest_submission.score,
            wrong_count_by_topic_axis=wrong_count_by_topic_axis,
            wrong_count_by_source_date=wrong_count_by_source_date,
            wrong_count_by_question_profile=wrong_count_by_question_profile,
        ),
        representative_wrong_examples=[
            WeeklyLearnerMemoWrongExample(
                question=result.question,
                selected_answer_text=_selected_answer_text(result),
                correct_answer_text=result.answer_text,
                explanation=result.explanation,
                topic_axis_label=result.topic_axis_label,
                source_date=result.source_date,
            )
            for result in wrong_results[:5]
        ],
        recommended_review_candidates=_select_review_candidates(
            guide=guide,
            topic_set=topic_set,
            wrong_results=wrong_results,
        ),
    )


def _normalize_ready_memo(
    memo: WeeklyLearnerMemo,
    context: WeeklyLearnerMemoInput,
) -> WeeklyLearnerMemo:
    fallback = MockWeeklyLearnerMemoGenerator().generate(context)
    recommended_review_points = [point.strip() for point in memo.recommended_review_points if point.strip()][:3]
    if not recommended_review_points:
        recommended_review_points = context.recommended_review_candidates[:3]
    if not recommended_review_points:
        recommended_review_points = fallback.recommended_review_points[:3]
    return WeeklyLearnerMemo(
        status="ready",
        headline=memo.headline.strip() or fallback.headline,
        summary=memo.summary.strip() or fallback.summary,
        recommended_review_points=recommended_review_points,
        focus_topics=context.submission_summary.wrong_count_by_topic_axis[:3],
        focus_dates=context.submission_summary.wrong_count_by_source_date[:3],
    )


def _sorted_topic_focuses(counter: Counter[str]) -> list[WeeklyLearnerMemoFocusTopic]:
    return [
        WeeklyLearnerMemoFocusTopic(label=label, wrong_count=count)
        for label, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _sorted_date_focuses(counter: Counter[str]) -> list[WeeklyLearnerMemoFocusDate]:
    return [
        WeeklyLearnerMemoFocusDate(source_date=source_date, wrong_count=count)
        for source_date, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _base_review_points(guide: WeeklyGuide, topic_set: WeeklyTopicSet) -> list[str]:
    points = [point.strip() for point in guide.review_points if point.strip()]
    if points:
        return points
    return [axis.label for axis in topic_set.topic_axes if axis.label]


def _select_review_candidates(
    *,
    guide: WeeklyGuide,
    topic_set: WeeklyTopicSet,
    wrong_results: list[WeeklyQuizReviewResult],
    limit: int = 3,
) -> list[str]:
    points = _base_review_points(guide, topic_set)
    if not points:
        return []

    axis_by_label = {axis.label: axis for axis in topic_set.topic_axes}
    weighted_terms: Counter[str] = Counter()
    for result in wrong_results:
        weighted_terms[result.topic_axis_label] += 3
        axis = axis_by_label.get(result.topic_axis_label)
        if axis is None:
            continue
        for term in axis.supporting_terms:
            weighted_terms[term] += 1

    ranked: list[tuple[int, int, str]] = []
    for index, point in enumerate(points):
        normalized_point = point.casefold()
        score = 0
        for term, weight in weighted_terms.items():
            if term and term.casefold() in normalized_point:
                score += weight
        ranked.append((score, index, point))

    selected: list[str] = []
    for score, _index, point in sorted(ranked, key=lambda item: (-item[0], item[1])):
        if score <= 0:
            continue
        selected.append(point)
        if len(selected) == limit:
            return selected

    for point in points:
        if point in selected:
            continue
        selected.append(point)
        if len(selected) == limit:
            break
    return selected


def _selected_answer_text(result: WeeklyQuizReviewResult) -> str:
    if result.selected_option_index is None:
        return "선택 없음"
    if 0 <= result.selected_option_index < len(result.options):
        return result.options[result.selected_option_index]
    return "선택 없음"
