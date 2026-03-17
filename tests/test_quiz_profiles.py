from __future__ import annotations

from stt_quiz_service.schemas import ChunkDocument, QuizItem
from stt_quiz_service.services.quiz_profiles import (
    allocate_profile_counts,
    build_profile_plan,
    determine_eligible_profiles,
    downgrade_weak_retests,
    is_single_answer_wording,
    is_discriminative_retest_item,
    validate_quiz_items,
)
from stt_quiz_service.storage.repository import CorpusSelection


def _lecture(**overrides):
    base = {
        "corpus_id": "2026-02-02",
        "date": "2026-02-02",
        "subject": "Java",
        "content": "Java IO, Java NIO",
        "learning_goal": "Java IO와 NIO의 차이를 비교하고 구분한다",
        "summary": "Java IO와 NIO의 차이, 구분, 비교를 다룬 강의",
        "topic_count": 1,
    }
    base.update(overrides)
    return CorpusSelection(**base)


def _chunk(text: str, chunk_id: str = "c1"):
    return ChunkDocument(
        chunk_id=chunk_id,
        corpus_id="2026-02-02",
        chunk_order=0,
        text=text,
        source_span="0:0",
        metadata={},
    )


def test_retest_profile_eligible_when_confusion_signals_exist():
    lecture = _lecture()
    chunks = [_chunk("IO와 NIO의 차이를 비교하고 헷갈리기 쉬운 포인트를 구분한다.")]
    eligible = determine_eligible_profiles(lecture, chunks)
    assert "basic_eval_4" in eligible
    assert "review_5" in eligible
    assert "retest_5" in eligible


def test_retest_profile_not_eligible_without_confusion_signals():
    lecture = _lecture(
        content="Java IO, Java NIO",
        learning_goal="Java IO와 NIO의 기본 개념을 설명한다",
        summary="Java IO와 NIO 개념 소개",
    )
    chunks = [_chunk("Java IO와 Java NIO의 기본 개념을 소개한다.")]
    eligible = determine_eligible_profiles(lecture, chunks)
    assert "basic_eval_4" in eligible
    assert "review_5" in eligible
    assert "retest_5" not in eligible


def test_allocate_profile_counts_preserves_minimum_and_total():
    counts = allocate_profile_counts(
        5,
        ["basic_eval_4", "review_5", "retest_5"],
        preferred_choice_count=None,
    )
    assert sum(counts.values()) == 5
    assert counts["basic_eval_4"] >= 1
    assert len([profile for profile, count in counts.items() if count > 0]) == 3


def test_build_profile_plan_uses_two_profiles_when_retest_is_ineligible():
    lecture = _lecture(
        learning_goal="Java IO와 NIO의 기본 개념을 설명한다",
        summary="Java IO와 NIO 개념 소개",
    )
    chunks = [_chunk("Java IO와 Java NIO의 기본 개념을 소개한다.", "c1")]
    plan = build_profile_plan(lecture, chunks, num_questions=5, preferred_choice_count=None)
    assert "retest_5" not in plan["eligible_profiles"]
    assert len([profile for profile, count in plan["profile_counts"].items() if count > 0]) == 2


def test_retest_item_requires_discriminative_signals():
    strong_item = QuizItem(
        question_profile="retest_5",
        choice_count=5,
        question="IO와 NIO의 차이에 대한 설명으로 옳지 않은 것을 고르시오.",
        options=["정답", "보기2", "보기3", "보기4", "보기5"],
        answer_index=0,
        answer_text="정답",
        explanation="강의에서는 두 개념의 차이와 구분 포인트를 강조했다.",
        difficulty="hard",
        evidence_chunk_ids=["c1"],
        learning_goal="goal",
    )
    weak_item = strong_item.model_copy(
        update={
            "question": "IO에 대한 설명은 무엇인가?",
            "explanation": "강의 내용을 요약한다.",
        }
    )
    assert is_discriminative_retest_item(strong_item)
    assert not is_discriminative_retest_item(weak_item)


def test_weak_retest_items_are_downgraded_to_review():
    weak_item = QuizItem(
        question_profile="retest_5",
        choice_count=5,
        question="IO에 대한 설명은 무엇인가?",
        options=["정답", "보기2", "보기3", "보기4", "보기5"],
        answer_index=0,
        answer_text="정답",
        explanation="강의 내용을 요약한다.",
        difficulty="hard",
        evidence_chunk_ids=["c1"],
        learning_goal="goal",
    )
    items, counts = downgrade_weak_retests(
        [weak_item],
        eligible_profiles=["basic_eval_4", "review_5", "retest_5"],
        expected_profile_counts={"retest_5": 1, "review_5": 2},
    )
    assert items[0].question_profile == "review_5"
    assert items[0].choice_count == 5
    assert counts == {"review_5": 3}


def test_multi_answer_wording_is_rejected():
    item = QuizItem(
        question_profile="review_5",
        choice_count=5,
        question="자바에서 입출력 처리에 사용되는 패키지를 모두 고르시오.",
        options=["java.io", "java.net", "java.nio", "java.util", "java.sql"],
        answer_index=0,
        answer_text="java.io",
        explanation="다중선택형처럼 읽히는 문장을 금지한다.",
        difficulty="medium",
        evidence_chunk_ids=["c1"],
        learning_goal="goal",
    )
    assert not is_single_answer_wording(item)
    try:
        validate_quiz_items(
            [item],
            expected_num_questions=1,
            eligible_profiles=["review_5"],
            expected_profile_counts={"review_5": 1},
        )
    except ValueError as exc:
        assert "multiple answers" in str(exc)
    else:
        raise AssertionError("validate_quiz_items should reject multi-answer wording")
