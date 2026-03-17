from __future__ import annotations

from collections import Counter
from math import floor
import re
from typing import Literal

from stt_quiz_service.schemas import ChunkDocument, QuizItem
from stt_quiz_service.storage.repository import CorpusSelection
from stt_quiz_service.services.retrieval import extract_concepts


QuestionProfile = Literal["basic_eval_4", "review_5", "retest_5"]

PROFILE_WEIGHTS: dict[QuestionProfile, float] = {
    "basic_eval_4": 0.35,
    "review_5": 0.40,
    "retest_5": 0.25,
}
PROFILE_PRIORITY: list[QuestionProfile] = ["review_5", "basic_eval_4", "retest_5"]
PROFILE_CHOICE_COUNT: dict[QuestionProfile, int] = {
    "basic_eval_4": 4,
    "review_5": 5,
    "retest_5": 5,
}
RETEST_SIGNAL_RE = re.compile(
    r"(차이|비교|반면|구분|혼동|헷갈|오해|주의|반대로|vs|대조|구별|틀린|옳지 않은|잘못된)"
)
MULTI_ANSWER_SIGNAL_RE = re.compile(
    r"(모두\s*고르|모두\s*선택|해당하는\s*것을\s*모두|옳은\s*것을\s*모두|맞는\s*것을\s*모두|복수\s*선택|둘\s*이상|2개\s*이상)"
)


def build_profile_plan(
    lecture: CorpusSelection,
    chunks: list[ChunkDocument],
    *,
    num_questions: int,
    preferred_choice_count: int | None,
) -> dict[str, object]:
    concepts = extract_concepts(lecture, chunks)
    eligible_profiles = determine_eligible_profiles(lecture, chunks, concepts)
    profile_counts = allocate_profile_counts(
        num_questions,
        eligible_profiles,
        preferred_choice_count=preferred_choice_count,
    )
    profile_sequence = expand_profile_counts(profile_counts)
    return {
        "concepts": concepts,
        "eligible_profiles": eligible_profiles,
        "profile_counts": profile_counts,
        "profile_sequence": profile_sequence,
    }


def determine_eligible_profiles(
    lecture: CorpusSelection,
    chunks: list[ChunkDocument],
    concepts: list[str] | None = None,
) -> list[QuestionProfile]:
    concepts = concepts or extract_concepts(lecture, chunks)
    eligible: list[QuestionProfile] = []
    if chunks:
        eligible.append("basic_eval_4")
    if len(concepts) >= 2:
        eligible.append("review_5")
    if len(concepts) >= 2 and _has_retest_signals(lecture, chunks):
        eligible.append("retest_5")
    return eligible or ["basic_eval_4"]


def allocate_profile_counts(
    num_questions: int,
    eligible_profiles: list[QuestionProfile],
    *,
    preferred_choice_count: int | None,
) -> dict[QuestionProfile, int]:
    adjusted_weights = dict(PROFILE_WEIGHTS)
    if preferred_choice_count == 4:
        adjusted_weights["basic_eval_4"] += 0.15
        adjusted_weights["review_5"] = max(0.05, adjusted_weights["review_5"] - 0.05)
        adjusted_weights["retest_5"] = max(0.05, adjusted_weights["retest_5"] - 0.10)
    elif preferred_choice_count == 5:
        adjusted_weights["basic_eval_4"] = max(0.05, adjusted_weights["basic_eval_4"] - 0.10)
        adjusted_weights["review_5"] += 0.05
        adjusted_weights["retest_5"] += 0.05

    counts: dict[QuestionProfile, int] = {profile: 0 for profile in eligible_profiles}
    min_required = 1 if len(eligible_profiles) > 1 else 0
    for profile in eligible_profiles:
        counts[profile] = min_required
    remaining = num_questions - sum(counts.values())
    if remaining <= 0:
        return counts

    total_weight = sum(adjusted_weights[profile] for profile in eligible_profiles)
    raw_allocations: dict[QuestionProfile, float] = {
        profile: remaining * adjusted_weights[profile] / total_weight for profile in eligible_profiles
    }
    residuals: dict[QuestionProfile, float] = {}
    for profile in eligible_profiles:
        whole = floor(raw_allocations[profile])
        counts[profile] += whole
        residuals[profile] = raw_allocations[profile] - whole

    leftover = num_questions - sum(counts.values())
    if leftover > 0:
        ranked_profiles = sorted(
            eligible_profiles,
            key=lambda profile: (
                residuals[profile],
                -PROFILE_PRIORITY.index(profile),
            ),
            reverse=True,
        )
        for profile in ranked_profiles:
            if leftover == 0:
                break
            counts[profile] += 1
            leftover -= 1

    if leftover > 0:
        for profile in PROFILE_PRIORITY:
            if profile in counts and leftover > 0:
                counts[profile] += 1
                leftover -= 1
    return counts


def expand_profile_counts(profile_counts: dict[QuestionProfile, int]) -> list[QuestionProfile]:
    remaining = dict(profile_counts)
    sequence: list[QuestionProfile] = []
    while sum(remaining.values()) > 0:
        ranked = sorted(
            [profile for profile, count in remaining.items() if count > 0],
            key=lambda profile: (
                remaining[profile],
                -PROFILE_PRIORITY.index(profile),
            ),
            reverse=True,
        )
        for profile in ranked:
            if remaining[profile] > 0:
                sequence.append(profile)
                remaining[profile] -= 1
    return sequence


def summarize_profile_distribution(items: list[QuizItem]) -> dict[str, int]:
    counter = Counter(item.question_profile for item in items)
    return dict(counter)


def downgrade_weak_retests(
    items: list[QuizItem],
    *,
    eligible_profiles: list[QuestionProfile],
    expected_profile_counts: dict[QuestionProfile, int] | None = None,
) -> tuple[list[QuizItem], dict[QuestionProfile, int] | None]:
    normalized_items: list[QuizItem] = []
    adjusted_counts = dict(expected_profile_counts) if expected_profile_counts else None
    for item in items:
        if item.question_profile == "retest_5" and not is_discriminative_retest_item(item):
            if "review_5" not in eligible_profiles:
                normalized_items.append(item)
                continue
            normalized_items.append(
                item.model_copy(
                    update={
                        "question_profile": "review_5",
                        "choice_count": PROFILE_CHOICE_COUNT["review_5"],
                    }
                )
            )
            if adjusted_counts:
                adjusted_counts["retest_5"] = max(0, adjusted_counts.get("retest_5", 0) - 1)
                adjusted_counts["review_5"] = adjusted_counts.get("review_5", 0) + 1
            continue
        normalized_items.append(item)
    if adjusted_counts:
        adjusted_counts = {profile: count for profile, count in adjusted_counts.items() if count > 0}
    return normalized_items, adjusted_counts


def validate_quiz_items(
    items: list[QuizItem],
    *,
    expected_num_questions: int,
    eligible_profiles: list[QuestionProfile],
    expected_profile_counts: dict[QuestionProfile, int] | None = None,
) -> None:
    if len(items) != expected_num_questions:
        raise ValueError(
            f"Invalid quiz size from model: expected {expected_num_questions}, got {len(items)}"
        )
    if not items:
        raise ValueError("Quiz generation returned no items")

    distribution = summarize_profile_distribution(items)
    for item in items:
        if item.question_profile not in eligible_profiles:
            raise ValueError(f"Ineligible question profile returned: {item.question_profile}")
        expected_choice_count = PROFILE_CHOICE_COUNT[item.question_profile]
        if item.choice_count != expected_choice_count:
            raise ValueError(
                f"Invalid choice_count for {item.question_profile}: "
                f"expected {expected_choice_count}, got {item.choice_count}"
            )
        if len(item.options) != item.choice_count:
            raise ValueError(
                f"Option length mismatch for {item.question_profile}: "
                f"expected {item.choice_count}, got {len(item.options)}"
            )
        if not is_single_answer_wording(item):
            raise ValueError("Question wording implies multiple answers")
        if item.question_profile == "retest_5" and not is_discriminative_retest_item(item):
            raise ValueError("Retest item is not discriminative enough")

    if expected_profile_counts:
        for profile, expected_count in expected_profile_counts.items():
            if distribution.get(profile, 0) != expected_count:
                raise ValueError(
                    f"Profile count mismatch for {profile}: "
                    f"expected {expected_count}, got {distribution.get(profile, 0)}"
                )


def is_discriminative_retest_item(item: QuizItem) -> bool:
    signal_text = f"{item.question} {item.explanation} {' '.join(item.options)}"
    return (
        item.question_profile == "retest_5"
        and len(set(item.options)) == len(item.options)
        and bool(RETEST_SIGNAL_RE.search(signal_text))
    )


def is_single_answer_wording(item: QuizItem) -> bool:
    signal_text = f"{item.question} {item.explanation}"
    return not MULTI_ANSWER_SIGNAL_RE.search(signal_text)


def _has_retest_signals(lecture: CorpusSelection, chunks: list[ChunkDocument]) -> bool:
    corpus = " ".join([lecture.content, lecture.learning_goal, lecture.summary] + [chunk.text for chunk in chunks[:8]])
    return bool(RETEST_SIGNAL_RE.search(corpus))
