from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from stt_quiz_service.api.app import create_app
from stt_quiz_service.schemas import DailyTermCandidate, DailyTermCandidates, WeeklyQuizSet
from stt_quiz_service.services.weekly_baseline_sync import sync_weekly_read_model
from stt_quiz_service.storage.models import (
    WeeklyQuizSubmissionAnswerRecord,
    WeeklyQuizSubmissionAttemptRecord,
)


def _build_synced_week1_client(monkeypatch, tmp_path):
    monkeypatch.setenv("STT_QUIZ_DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("STT_QUIZ_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("STT_QUIZ_LLM_BACKEND", "mock")
    app = create_app()
    sync_weekly_read_model(
        app.state.orchestrator.repository,
        curriculum_path=app.state.orchestrator.settings.curriculum_path,
        prepared_dir=Path("artifacts/preprocessed"),
        week_id="1",
        topic_set_path=Path("artifacts/pipeline_state/weekly_1_topic_set.json"),
        guide_path=Path("artifacts/pipeline_state/weekly_1_guide.json"),
        quiz_path=Path("artifacts/pipeline_state/weekly_1_quiz.json"),
        report_path=Path("artifacts/pipeline_state/weekly_1_report.json"),
    )
    return app, TestClient(app)


def _submit_answers(client: TestClient, answers: list[dict[str, int | str]]):
    return client.post("/weekly-quiz/1/submit", json={"answers": answers})


def _build_full_submit_answers(
    app,
    client: TestClient,
    *,
    wrong_item_ids: set[str] | None = None,
):
    wrong_item_ids = wrong_item_ids or set()
    learner_items = client.get("/weekly-quiz/1").json()["items"]
    full_items = app.state.orchestrator.get_weekly_quiz("1").items
    answers = []
    for learner_item, full_item in zip(learner_items, full_items):
        selected_option_index = full_item.answer_index
        if learner_item["item_id"] in wrong_item_ids:
            selected_option_index = (full_item.answer_index + 1) % learner_item["choice_count"]
        answers.append(
            {
                "item_id": learner_item["item_id"],
                "selected_option_index": selected_option_index,
            }
        )
    return learner_items, full_items, answers


def test_api_end_to_end(monkeypatch, tmp_path):
    monkeypatch.setenv("STT_QUIZ_DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("STT_QUIZ_EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("STT_QUIZ_LLM_BACKEND", "mock")
    app = create_app()
    client = TestClient(app)

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["database_url"].endswith("api.db")

    weeks_before_response = client.get("/weeks")
    assert weeks_before_response.status_code == 200
    assert weeks_before_response.json() == []

    prepare_response = client.post(
        "/pipeline/prepare",
        json={
            "transcripts_root": "NLP_Task2/강의 스크립트",
            "curriculum_path": "NLP_Task2/강의 커리큘럼.csv",
            "output_dir": str(tmp_path / "prepared"),
        },
    )
    assert prepare_response.status_code == 200

    index_response = client.post("/pipeline/index", json={"corpus_ids": None})
    assert index_response.status_code == 200

    lectures_response = client.get("/lectures")
    assert lectures_response.status_code == 200
    lectures = lectures_response.json()
    assert lectures

    generate_response = client.post(
        "/pipeline/generate",
        json={
            "corpus_ids": ["2026-02-24"],
            "mode": "rag",
            "num_questions": 5,
            "choice_count": None,
        },
    )
    assert generate_response.status_code == 200

    bundle_response = client.get("/bundle/2026-02-24")
    assert bundle_response.status_code == 200
    payload = bundle_response.json()
    assert payload["quiz_set"]["items"]
    assert payload["run"]["retrieved_chunk_ids"]
    assert payload["run"]["retrieval_query"]
    assert payload["run"]["retrieval_hits"]
    assert payload["run"]["embedder_provider"]
    assert payload["run"]["profile_distribution"]
    assert all("question_profile" in item for item in payload["quiz_set"]["items"])
    assert all("choice_count" in item for item in payload["quiz_set"]["items"])
    assert all(item["choice_count"] == len(item["options"]) for item in payload["quiz_set"]["items"])
    assert payload["run"]["retrieval_hits"][0]["rank"] == 1
    assert payload["run"]["retrieval_hits"][0]["chunk_id"] in payload["run"]["retrieved_chunk_ids"]

    audit_response = client.get("/audit/events")
    assert audit_response.status_code == 200
    events = audit_response.json()
    assert any(event["event_type"] == "prepare" and event["status"] == "success" for event in events)
    assert any(event["event_type"] == "index" and event["status"] == "success" for event in events)
    assert any(event["event_type"] == "pipeline_generate" and event["status"] == "success" for event in events)
    assert any(
        event["event_type"] == "generation" and event["status"] == "success"
        for event in events
    )
    assert any(
        event["event_type"] == "generation"
        and event["status"] == "success"
        and event["details"].get("profile_distribution")
        for event in events
    )

    def fake_extract(self, *, corpus_id: str, week_id: str, cleaned_text: str, chunks):
        return DailyTermCandidates(
            corpus_id=corpus_id,
            week_id=week_id,
            candidates=[
                DailyTermCandidate(
                    term=f"{corpus_id} 핵심 주제",
                    score=0.9,
                    evidence_chunk_ids=[chunk.chunk_id for chunk in chunks[:2]],
                )
            ],
        )

    monkeypatch.setattr(type(client.app.state.orchestrator.candidate_extractor), "extract", fake_extract)

    week_id = client.app.state.orchestrator.list_weeks()[0].week_id

    extract_response = client.post("/pipeline/extract-term-candidates", json={"corpus_ids": None})
    assert extract_response.status_code == 200

    build_weekly_topics = client.post("/pipeline/build-weekly-topics", json={"week_ids": [week_id]})
    assert build_weekly_topics.status_code == 200

    generate_weekly_guides = client.post("/pipeline/generate-weekly-guides", json={"week_ids": [week_id]})
    assert generate_weekly_guides.status_code == 200

    generate_weekly_quizzes = client.post(
        "/pipeline/generate-weekly-quizzes",
        json={"week_ids": [week_id], "num_questions": 5},
    )
    assert generate_weekly_quizzes.status_code == 200

    weekly_topics = client.get(f"/weekly-topics/{week_id}")
    assert weekly_topics.status_code == 200
    assert weekly_topics.json()["topic_axes"]

    weekly_guide = client.get(f"/weekly-guide/{week_id}")
    assert weekly_guide.status_code == 200
    assert weekly_guide.json()["learning_paragraph"]

    weekly_quiz = client.get(f"/weekly-quiz/{week_id}")
    assert weekly_quiz.status_code == 200
    assert weekly_quiz.json()["items"]
    assert "answer_index" not in weekly_quiz.json()["items"][0]
    assert "answer_text" not in weekly_quiz.json()["items"][0]
    assert "explanation" not in weekly_quiz.json()["items"][0]

    weekly_report = client.get(f"/weekly-report/{week_id}")
    assert weekly_report.status_code == 200
    assert weekly_report.json()["question_type_metrics"]
    assert weekly_report.json()["learner_memo"]["status"] == "no_submission"

    weeks_response = client.get("/weeks")
    assert weeks_response.status_code == 200
    assert [week["week_id"] for week in weeks_response.json()] == [week_id]

    weekly_bundle = client.get(f"/weekly-bundle/{week_id}")
    assert weekly_bundle.status_code == 200
    assert weekly_bundle.json()["quiz_set"]["items"]


def test_api_serves_only_ready_accepted_weekly_baseline(monkeypatch, tmp_path):
    _app, client = _build_synced_week1_client(monkeypatch, tmp_path)

    weeks_response = client.get("/weeks")
    assert weeks_response.status_code == 200
    assert weeks_response.json() == [
        {
            "week_id": "1",
            "week": 1,
            "corpus_ids": [
                "2026-02-02",
                "2026-02-03",
                "2026-02-04",
                "2026-02-05",
                "2026-02-06",
            ],
            "dates": [
                "2026-02-02",
                "2026-02-03",
                "2026-02-04",
                "2026-02-05",
                "2026-02-06",
            ],
            "subject": "객체지향 프로그래밍 / Front-End Programming",
            "content": (
                "데코레이터 패턴, 옵저버 패턴 / 파사드 패턴, 전략 패턴 / "
                "HTML, CSS를 이용한 화면 설계 및 표현 / JavaScript 기본 문법"
            ),
            "learning_goal": (
                "데코레이터 패턴과 옵저버 패턴의 구조를 이해하고 Java로 구현할 수 있다 / "
                "파사드 패턴과 전략 패턴의 차이를 설명하고 실습 예제에 적용할 수 있다 / "
                "HTML 구조와 CSS 스타일링 기법을 이해하고 기본 웹 페이지를 구현할 수 있다 / "
                "JavaScript의 변수, 함수, 이벤트 처리 등 기본 문법을 이해하고 활용할 수 있다"
            ),
        }
    ]

    bundle_response = client.get("/weekly-bundle/1")
    assert bundle_response.status_code == 200
    bundle = bundle_response.json()
    weekly_quiz_response = client.get("/weekly-quiz/1")
    assert weekly_quiz_response.status_code == 200
    weekly_quiz_payload = weekly_quiz_response.json()
    expected_quiz_payload = WeeklyQuizSet.model_validate_json(
        Path("artifacts/pipeline_state/weekly_1_quiz.json").read_text(encoding="utf-8")
    ).to_learner_set().model_dump()

    assert bundle["topics"] == json.loads(Path("artifacts/pipeline_state/weekly_1_topic_set.json").read_text(encoding="utf-8"))
    assert bundle["guide"] == json.loads(Path("artifacts/pipeline_state/weekly_1_guide.json").read_text(encoding="utf-8"))
    assert bundle["quiz_set"] == expected_quiz_payload
    assert bundle["report"] == json.loads(Path("artifacts/pipeline_state/weekly_1_report.json").read_text(encoding="utf-8"))
    assert weekly_quiz_payload == expected_quiz_payload
    assert all(item["item_id"] for item in weekly_quiz_payload["items"])
    assert len({item["item_id"] for item in weekly_quiz_payload["items"]}) == len(weekly_quiz_payload["items"])
    assert "answer_index" not in weekly_quiz_payload["items"][0]
    assert "answer_text" not in weekly_quiz_payload["items"][0]
    assert "explanation" not in weekly_quiz_payload["items"][0]
    assert "answer_index" not in bundle["quiz_set"]["items"][0]
    assert "answer_text" not in bundle["quiz_set"]["items"][0]
    assert "explanation" not in bundle["quiz_set"]["items"][0]


def test_weekly_quiz_latest_submission_returns_404_when_absent(monkeypatch, tmp_path):
    _app, client = _build_synced_week1_client(monkeypatch, tmp_path)

    response = client.get("/weekly-quiz/1/latest-submission")
    assert response.status_code == 404
    assert "No weekly quiz submission found for week_id: 1" in response.text


def test_weekly_report_returns_no_submission_learner_memo(monkeypatch, tmp_path):
    _app, client = _build_synced_week1_client(monkeypatch, tmp_path)

    response = client.get("/weekly-report/1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["week_id"] == "1"
    assert payload["notes"] == [
        "학습자 응답 데이터가 없어 문항 유형별 커버리지 기준으로 리포트를 구성했습니다."
    ]
    assert payload["learner_memo"]["status"] == "no_submission"
    assert payload["learner_memo"]["focus_topics"] == []
    assert payload["learner_memo"]["focus_dates"] == []
    assert payload["learner_memo"]["recommended_review_points"]


def test_weekly_quiz_submit_scores_and_saves_attempt(monkeypatch, tmp_path):
    app, client = _build_synced_week1_client(monkeypatch, tmp_path)
    quiz_response = client.get("/weekly-quiz/1")
    assert quiz_response.status_code == 200
    learner_items = quiz_response.json()["items"]
    full_items = app.state.orchestrator.get_weekly_quiz("1").items

    first_item = learner_items[0]
    second_item = learner_items[1]
    third_item = learner_items[2]
    first_full_item = full_items[0]
    second_full_item = full_items[1]
    third_full_item = full_items[2]

    submit_answers = []
    for learner_item, full_item in zip(learner_items, full_items):
        selected_option_index = full_item.answer_index
        if learner_item["item_id"] == second_item["item_id"]:
            selected_option_index = (second_full_item.answer_index + 1) % second_item["choice_count"]
        submit_answers.append(
            {
                "item_id": learner_item["item_id"],
                "selected_option_index": selected_option_index,
            }
        )

    submit_response = client.post("/weekly-quiz/1/submit", json={"answers": submit_answers})
    assert submit_response.status_code == 200
    payload = submit_response.json()

    assert payload["week_id"] == "1"
    assert payload["submitted_at"]
    assert payload["total_questions"] == 25
    assert payload["correct_count"] == 24
    assert payload["score"] == 96
    assert len(payload["results"]) == 25
    assert payload["learner_memo"]["status"] == "ready"
    assert payload["learner_memo"]["focus_topics"][0]["label"] == second_full_item.topic_axis_label
    assert payload["learner_memo"]["focus_dates"][0]["source_date"] == second_full_item.source_date
    assert payload["learner_memo"]["recommended_review_points"]

    results_by_id = {result["item_id"]: result for result in payload["results"]}
    assert results_by_id[first_item["item_id"]] == {
        "item_id": first_item["item_id"],
        "selected_option_index": first_full_item.answer_index,
        "correct_option_index": first_full_item.answer_index,
        "answer_text": first_full_item.answer_text,
        "explanation": first_full_item.explanation,
        "is_correct": True,
    }
    assert results_by_id[second_item["item_id"]]["selected_option_index"] != second_full_item.answer_index
    assert results_by_id[second_item["item_id"]]["correct_option_index"] == second_full_item.answer_index
    assert results_by_id[second_item["item_id"]]["answer_text"] == second_full_item.answer_text
    assert results_by_id[second_item["item_id"]]["explanation"] == second_full_item.explanation
    assert results_by_id[second_item["item_id"]]["is_correct"] is False
    assert results_by_id[third_item["item_id"]] == {
        "item_id": third_item["item_id"],
        "selected_option_index": third_full_item.answer_index,
        "correct_option_index": third_full_item.answer_index,
        "answer_text": third_full_item.answer_text,
        "explanation": third_full_item.explanation,
        "is_correct": True,
    }

    with app.state.orchestrator.repository.session_factory() as db:
        attempt = db.get(WeeklyQuizSubmissionAttemptRecord, payload["attempt_id"])
        assert attempt is not None
        assert attempt.week_id == "1"
        assert attempt.total_questions == 25
        assert attempt.correct_count == 24
        assert attempt.score == 96
        answer_rows = db.execute(
            select(WeeklyQuizSubmissionAnswerRecord)
            .where(WeeklyQuizSubmissionAnswerRecord.attempt_id == payload["attempt_id"])
            .order_by(WeeklyQuizSubmissionAnswerRecord.question_order)
        ).scalars().all()
        assert len(answer_rows) == 25
        assert answer_rows[0].item_id == first_item["item_id"]
        assert answer_rows[0].selected_option_index == first_full_item.answer_index
        assert answer_rows[1].item_id == second_item["item_id"]
        assert answer_rows[1].is_correct is False
        assert answer_rows[2].item_id == third_item["item_id"]
        assert answer_rows[2].selected_option_index == third_full_item.answer_index

    latest_response = client.get("/weekly-quiz/1/latest-submission")
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert latest_payload["attempt_id"] == payload["attempt_id"]
    assert latest_payload["week_id"] == "1"
    assert latest_payload["total_questions"] == 25
    assert latest_payload["correct_count"] == 24
    assert latest_payload["score"] == 96
    assert latest_payload["submitted_at"]
    assert len(latest_payload["results"]) == 25
    assert latest_payload["results"][0] == {
        "item_id": first_item["item_id"],
        "question": first_full_item.question,
        "options": first_full_item.options,
        "selected_option_index": first_full_item.answer_index,
        "correct_option_index": first_full_item.answer_index,
        "answer_text": first_full_item.answer_text,
        "explanation": first_full_item.explanation,
        "is_correct": True,
        "topic_axis_label": first_full_item.topic_axis_label,
        "source_corpus_id": first_full_item.source_corpus_id,
        "source_date": first_full_item.source_date,
        "learning_goal": first_full_item.learning_goal,
        "learning_goal_source": first_full_item.learning_goal_source,
        "retrieved_chunk_ids": first_full_item.retrieved_chunk_ids,
        "evidence_chunk_ids": first_full_item.evidence_chunk_ids,
    }

    attempt_response = client.get(f"/weekly-quiz/1/attempts/{payload['attempt_id']}")
    assert attempt_response.status_code == 200
    assert attempt_response.json() == latest_payload

    report_response = client.get("/weekly-report/1")
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["learner_memo"]["status"] == "ready"
    assert report_payload["learner_memo"]["focus_topics"][0]["label"] == second_full_item.topic_axis_label
    assert report_payload["learner_memo"]["focus_dates"][0]["source_date"] == second_full_item.source_date
    assert report_payload["learner_memo"]["recommended_review_points"]


def test_weekly_report_returns_all_correct_learner_memo(monkeypatch, tmp_path):
    app, client = _build_synced_week1_client(monkeypatch, tmp_path)
    _learner_items, _full_items, answers = _build_full_submit_answers(app, client)

    submit_response = _submit_answers(client, answers)
    assert submit_response.status_code == 200
    assert submit_response.json()["learner_memo"]["status"] == "all_correct"

    report_response = client.get("/weekly-report/1")
    assert report_response.status_code == 200
    learner_memo = report_response.json()["learner_memo"]
    assert learner_memo["status"] == "all_correct"
    assert learner_memo["focus_topics"] == []
    assert learner_memo["focus_dates"] == []
    assert learner_memo["recommended_review_points"]


def test_weekly_report_learner_memo_tracks_latest_submission(monkeypatch, tmp_path):
    app, client = _build_synced_week1_client(monkeypatch, tmp_path)
    learner_items, full_items, answers = _build_full_submit_answers(app, client)
    wrong_item_id = learner_items[0]["item_id"]
    wrong_full_item = full_items[0]
    for answer in answers:
        if answer["item_id"] == wrong_item_id:
            answer["selected_option_index"] = (wrong_full_item.answer_index + 1) % learner_items[0]["choice_count"]
            break

    first_submit_response = _submit_answers(client, answers)
    assert first_submit_response.status_code == 200
    assert first_submit_response.json()["learner_memo"]["status"] == "ready"

    first_report = client.get("/weekly-report/1")
    assert first_report.status_code == 200
    first_memo = first_report.json()["learner_memo"]
    assert first_memo["status"] == "ready"

    _learner_items, _full_items, correct_answers = _build_full_submit_answers(app, client)
    second_submit_response = _submit_answers(client, correct_answers)
    assert second_submit_response.status_code == 200
    assert second_submit_response.json()["learner_memo"]["status"] == "all_correct"

    second_report = client.get("/weekly-report/1")
    assert second_report.status_code == 200
    second_memo = second_report.json()["learner_memo"]
    assert second_memo["status"] == "all_correct"
    assert second_memo != first_memo


def test_weekly_quiz_submit_rejects_partial_answers(monkeypatch, tmp_path):
    app, client = _build_synced_week1_client(monkeypatch, tmp_path)
    learner_items = client.get("/weekly-quiz/1").json()["items"]
    full_items = app.state.orchestrator.get_weekly_quiz("1").items

    partial_answers = [
        {
            "item_id": learner_item["item_id"],
            "selected_option_index": full_item.answer_index,
        }
        for index, (learner_item, full_item) in enumerate(zip(learner_items, full_items), start=1)
        if index not in {3, 7}
    ]

    submit_response = client.post("/weekly-quiz/1/submit", json={"answers": partial_answers})
    assert submit_response.status_code == 422
    detail = submit_response.json()["detail"]
    assert "all questions must be answered before submit" in detail
    assert "missing_item_ids=" in detail
    assert f"'{learner_items[2]['item_id']}'" in detail
    assert f"'{learner_items[6]['item_id']}'" in detail
    assert "missing_question_numbers=[3, 7]" in detail

    with app.state.orchestrator.repository.session_factory() as db:
        attempts = db.execute(select(WeeklyQuizSubmissionAttemptRecord)).scalars().all()
        assert attempts == []


def test_weekly_quiz_attempt_fetch_rejects_week_mismatch(monkeypatch, tmp_path):
    app, client = _build_synced_week1_client(monkeypatch, tmp_path)
    learner_items = client.get("/weekly-quiz/1").json()["items"]
    full_items = app.state.orchestrator.get_weekly_quiz("1").items

    submit_response = client.post(
        "/weekly-quiz/1/submit",
        json={
            "answers": [
                {
                    "item_id": learner_item["item_id"],
                    "selected_option_index": full_item.answer_index,
                }
                for learner_item, full_item in zip(learner_items, full_items)
            ]
        },
    )
    assert submit_response.status_code == 200
    attempt_id = submit_response.json()["attempt_id"]

    mismatch_response = client.get(f"/weekly-quiz/2/attempts/{attempt_id}")
    assert mismatch_response.status_code == 404
    assert f"attempt_id {attempt_id} does not belong to week_id: 2" in mismatch_response.text


def test_weekly_quiz_submit_rejects_invalid_answers(monkeypatch, tmp_path):
    _app, client = _build_synced_week1_client(monkeypatch, tmp_path)
    quiz_response = client.get("/weekly-quiz/1")
    assert quiz_response.status_code == 200
    first_item = quiz_response.json()["items"][0]

    missing_item_id_response = client.post(
        "/weekly-quiz/1/submit",
        json={"answers": [{"selected_option_index": 0}]},
    )
    assert missing_item_id_response.status_code == 422

    duplicate_response = client.post(
        "/weekly-quiz/1/submit",
        json={
            "answers": [
                {"item_id": first_item["item_id"], "selected_option_index": 0},
                {"item_id": first_item["item_id"], "selected_option_index": 1},
            ]
        },
    )
    assert duplicate_response.status_code == 422
    assert "duplicate item_id answers are not allowed" in duplicate_response.text

    out_of_range_response = client.post(
        "/weekly-quiz/1/submit",
        json={
            "answers": [
                {
                    "item_id": first_item["item_id"],
                    "selected_option_index": first_item["choice_count"],
                }
            ]
        },
    )
    assert out_of_range_response.status_code == 422
    assert "selected_option_index is out of range" in out_of_range_response.text

    unknown_item_response = client.post(
        "/weekly-quiz/1/submit",
        json={"answers": [{"item_id": "missing-item", "selected_option_index": 0}]},
    )
    assert unknown_item_response.status_code == 422
    assert "unknown item_id" in unknown_item_response.text
