from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from stt_quiz_service.schemas import CorpusDocument, WeeklyGuide, WeeklyQuizSet, WeeklyReport, WeeklyTopicSet
from stt_quiz_service.services.ingestion import build_lecture_id, load_curriculum_rows
from stt_quiz_service.storage.models import LectureRecord
from stt_quiz_service.storage.repository import Repository


@dataclass(slots=True)
class WeeklyBaselineSyncResult:
    week_id: str
    lecture_count: int
    corpus_ids: list[str]
    topic_axis_count: int
    review_point_count: int
    quiz_item_count: int
    report_verified: bool


def _load_corpus_doc(prepared_dir: Path, corpus_id: str) -> CorpusDocument:
    path = prepared_dir / f"{corpus_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing prepared corpus JSON for weekly baseline sync: {path}")
    return CorpusDocument.model_validate_json(path.read_text(encoding="utf-8"))


def _validate_week_id(week_id: str, payload_week_id: str, *, label: str) -> None:
    if payload_week_id != week_id:
        raise ValueError(f"{label} week_id mismatch: expected={week_id} actual={payload_week_id}")


def sync_weekly_read_model(
    repository: Repository,
    *,
    curriculum_path: Path,
    prepared_dir: Path,
    week_id: str,
    topic_set_path: Path,
    guide_path: Path,
    quiz_path: Path,
    report_path: Path | None = None,
) -> WeeklyBaselineSyncResult:
    curriculum_rows = [row for row in load_curriculum_rows(curriculum_path) if str(row.week) == week_id]
    if not curriculum_rows:
        raise ValueError(f"No curriculum rows found for week_id={week_id}")

    expected_corpus_ids = sorted({row.date for row in curriculum_rows})
    corpus_by_id = {corpus_id: _load_corpus_doc(prepared_dir, corpus_id) for corpus_id in expected_corpus_ids}

    topic_set = WeeklyTopicSet.model_validate_json(topic_set_path.read_text(encoding="utf-8"))
    guide = WeeklyGuide.model_validate_json(guide_path.read_text(encoding="utf-8"))
    quiz_set = WeeklyQuizSet.model_validate_json(quiz_path.read_text(encoding="utf-8"))

    _validate_week_id(week_id, topic_set.week_id, label="weekly topic set")
    _validate_week_id(week_id, guide.week_id, label="weekly guide")
    _validate_week_id(week_id, quiz_set.week_id, label="weekly quiz")

    if sorted(quiz_set.corpus_ids) != expected_corpus_ids:
        raise ValueError(
            "weekly quiz corpus_ids mismatch: "
            f"expected={expected_corpus_ids} actual={sorted(quiz_set.corpus_ids)}"
        )

    with repository.session_factory.begin() as db:
        for row in curriculum_rows:
            corpus = corpus_by_id[row.date]
            db.merge(
                LectureRecord(
                    lecture_id=build_lecture_id(row.date, row.session),
                    corpus_id=row.date,
                    week=row.week,
                    date=row.date,
                    session=row.session,
                    subject=row.subject,
                    content=row.content,
                    learning_goal=row.learning_goal,
                    source_path=corpus.source_path,
                    cleaned_text=corpus.cleaned_text,
                    summary=corpus.summary,
                )
            )

    repository.save_weekly_topic_set(topic_set)
    repository.save_weekly_guide(guide)
    repository.save_weekly_quiz_set(quiz_set)

    report_verified = False
    if report_path is not None:
        expected_report = WeeklyReport.model_validate_json(report_path.read_text(encoding="utf-8"))
        actual_report = repository.get_weekly_report(week_id)
        if actual_report.model_dump() != expected_report.model_dump():
            raise ValueError(
                f"weekly report mismatch after sync for week_id={week_id}: "
                "generated report does not match the accepted artifact"
            )
        report_verified = True

    repository.log_audit_event(
        event_type="sync_weekly_read_model",
        status="success",
        details={
            "week_id": week_id,
            "lecture_count": len(curriculum_rows),
            "corpus_ids": expected_corpus_ids,
            "topic_set_path": str(topic_set_path),
            "guide_path": str(guide_path),
            "quiz_path": str(quiz_path),
            "report_path": str(report_path) if report_path is not None else "",
            "report_verified": report_verified,
        },
    )

    return WeeklyBaselineSyncResult(
        week_id=week_id,
        lecture_count=len(curriculum_rows),
        corpus_ids=expected_corpus_ids,
        topic_axis_count=len(topic_set.topic_axes),
        review_point_count=len(guide.review_points),
        quiz_item_count=len(quiz_set.items),
        report_verified=report_verified,
    )
