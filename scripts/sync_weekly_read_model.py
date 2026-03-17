from __future__ import annotations

import argparse
from pathlib import Path

from stt_quiz_service.config import load_settings
from stt_quiz_service.services.weekly_baseline_sync import sync_weekly_read_model
from stt_quiz_service.storage.db import build_engine, build_session_factory
from stt_quiz_service.storage.repository import Repository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week-id", default="1")
    parser.add_argument("--prepared-dir", default="artifacts/preprocessed")
    parser.add_argument("--topic-set-path", default="artifacts/pipeline_state/weekly_1_topic_set.json")
    parser.add_argument("--guide-path", default="artifacts/pipeline_state/weekly_1_guide.json")
    parser.add_argument("--quiz-path", default="artifacts/pipeline_state/weekly_1_quiz.json")
    parser.add_argument("--report-path", default="artifacts/pipeline_state/weekly_1_report.json")
    args = parser.parse_args()

    settings = load_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    repository = Repository(session_factory)
    repository.create_schema()

    result = sync_weekly_read_model(
        repository,
        curriculum_path=settings.curriculum_path,
        prepared_dir=Path(args.prepared_dir),
        week_id=args.week_id,
        topic_set_path=Path(args.topic_set_path),
        guide_path=Path(args.guide_path),
        quiz_path=Path(args.quiz_path),
        report_path=Path(args.report_path),
    )

    print(
        "weekly read model synced: "
        f"week_id={result.week_id} lectures={result.lecture_count} corpora={result.corpus_ids} "
        f"topic_axes={result.topic_axis_count} review_points={result.review_point_count} "
        f"quiz_items={result.quiz_item_count} report_verified={str(result.report_verified).lower()}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
