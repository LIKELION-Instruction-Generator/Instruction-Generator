from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from stt_quiz_service.schemas import (
    WeeklyQuizSet,
    WeeklyQuizSubmissionRequest,
    WeeklyQuizSubmissionResponse,
    WeeklyQuizSubmissionResult,
)


def grade_weekly_quiz_submission(
    quiz_set: WeeklyQuizSet,
    request: WeeklyQuizSubmissionRequest,
) -> WeeklyQuizSubmissionResponse:
    item_by_id = {item.item_id: item for item in quiz_set.items}
    selected_by_item_id: dict[str, int] = {}

    for answer in request.answers:
        item = item_by_id.get(answer.item_id)
        if item is None:
            raise ValueError(f"unknown item_id for week_id={quiz_set.week_id}: {answer.item_id}")
        if answer.selected_option_index >= item.choice_count:
            raise ValueError(
                "selected_option_index is out of range for "
                f"item_id={answer.item_id}: {answer.selected_option_index} >= {item.choice_count}"
            )
        selected_by_item_id[answer.item_id] = answer.selected_option_index

    missing_item_ids = [
        item.item_id
        for item in quiz_set.items
        if item.item_id not in selected_by_item_id
    ]
    if missing_item_ids:
        question_number_by_item_id = {
            item.item_id: index
            for index, item in enumerate(quiz_set.items, start=1)
        }
        missing_question_numbers = [
            question_number_by_item_id[item_id]
            for item_id in missing_item_ids
        ]
        raise ValueError(
            "all questions must be answered before submit: "
            f"missing_item_ids={missing_item_ids}, "
            f"missing_question_numbers={missing_question_numbers}"
        )

    results: list[WeeklyQuizSubmissionResult] = []
    correct_count = 0
    for item in quiz_set.items:
        selected_option_index = selected_by_item_id.get(item.item_id)
        is_correct = selected_option_index == item.answer_index if selected_option_index is not None else False
        if is_correct:
            correct_count += 1
        results.append(
            WeeklyQuizSubmissionResult(
                item_id=item.item_id,
                selected_option_index=selected_option_index,
                correct_option_index=item.answer_index,
                answer_text=item.answer_text,
                explanation=item.explanation,
                is_correct=is_correct,
            )
        )

    total_questions = len(quiz_set.items)
    score = int((correct_count * 100) / total_questions) if total_questions else 0
    return WeeklyQuizSubmissionResponse(
        attempt_id=uuid4().hex,
        week_id=quiz_set.week_id,
        submitted_at=datetime.now(timezone.utc).isoformat(),
        total_questions=total_questions,
        correct_count=correct_count,
        score=score,
        results=results,
    )
