from __future__ import annotations

import argparse
from pathlib import Path

from stt_quiz_service.config import load_settings
from stt_quiz_service.services.ingestion import load_curriculum_rows


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
    curriculum_path = settings.curriculum_path
    prepared_dir = Path(args.prepared_dir)

    required_paths = [
        curriculum_path,
        Path(args.topic_set_path),
        Path(args.guide_path),
        Path(args.quiz_path),
        Path(args.report_path),
    ]

    curriculum_rows = [row for row in load_curriculum_rows(curriculum_path) if str(row.week) == args.week_id]
    if not curriculum_rows:
        raise SystemExit(f"No curriculum rows found for week_id={args.week_id}: {curriculum_path}")

    corpus_ids = sorted({row.date for row in curriculum_rows})
    required_paths.extend(prepared_dir / f"{corpus_id}.json" for corpus_id in corpus_ids)

    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        print("runtime data bundle check: missing files", flush=True)
        for path in missing_paths:
            print(f"- {path}", flush=True)
        raise SystemExit(1)

    print(
        "runtime data bundle check: ok "
        f"week_id={args.week_id} corpus_ids={corpus_ids} "
        f"prepared_json={len(corpus_ids)} accepted_artifacts=4 curriculum={curriculum_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
