from __future__ import annotations

import argparse
from pathlib import Path
import sys

from _bootstrap import bootstrap_src_path

bootstrap_src_path()

from stt_quiz_service.config import load_settings
from stt_quiz_service.orchestrator import WorkflowOrchestrator
from stt_quiz_service.storage.db import build_engine, build_session_factory
from stt_quiz_service.storage.repository import Repository
from stt_quiz_service.services.topic_extraction import aggregate_weekly_candidates


DEFAULT_SEED_CANDIDATES = Path(
    "artifacts/runpod_fetch/gpu_backup_20260317/daily_term_candidates_export.jsonl"
)
DEFAULT_SEED_TOPIC_SET = Path(
    "artifacts/runpod_fetch/gpu_backup_20260317/weekly_1_topic_set.json"
)


def _expected_quiz_items(corpus_ids: list[str], *, min_questions_per_corpus: int) -> int:
    return len(corpus_ids) * min_questions_per_corpus


def _validate_seeded_imports(loaded_corpus_ids: list[str], expected_corpus_ids: list[str]) -> None:
    loaded = sorted(loaded_corpus_ids)
    expected = sorted(expected_corpus_ids)
    if loaded != expected:
        raise RuntimeError(
            "seeded baseline requires complete week-1 candidate seeds: "
            f"loaded={loaded} expected={expected}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week-id", default=None)
    parser.add_argument("--seeded-baseline", action="store_true")
    parser.add_argument(
        "--seed-candidates-file",
        default=str(DEFAULT_SEED_CANDIDATES),
    )
    parser.add_argument(
        "--seed-topic-file",
        default=str(DEFAULT_SEED_TOPIC_SET),
    )
    args = parser.parse_args()

    settings = load_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    repository = Repository(session_factory)
    orchestrator = WorkflowOrchestrator.build(settings, repository)
    orchestrator.bootstrap()

    weeks = orchestrator.list_weeks()
    if not weeks:
        print("No weeks found in DB.", flush=True)
        return 1

    week = next((item for item in weeks if item.week_id == args.week_id), weeks[0])
    print(f"weekly start: week_id={week.week_id} dates={week.dates} corpus_ids={week.corpus_ids}", flush=True)

    if args.seeded_baseline:
        if orchestrator.weekly_quiz_generator is None:
            raise RuntimeError(
                "seeded baseline requires LangChain strict-RAG quiz generator; "
                "OPENAI_API_KEY / GOOGLE_API_KEY and LangChain deps must be available"
            )
        loaded_corpus_ids = orchestrator.import_daily_term_candidate_seed(
            Path(args.seed_candidates_file),
            week_id=week.week_id,
            corpus_ids=week.corpus_ids,
        )
        _validate_seeded_imports(loaded_corpus_ids, week.corpus_ids)
        topic_set = orchestrator.import_weekly_topic_set_seed(Path(args.seed_topic_file))
        loaded_candidates = len(loaded_corpus_ids)
        print(
            f"seed_candidates_loaded=true loaded={loaded_candidates} expected={len(week.corpus_ids)}",
            flush=True,
        )
        print(
            f"seed_topic_set_loaded=true topic_axes={len(topic_set.topic_axes)}",
            flush=True,
        )
        print("candidate_extraction_skipped=true", flush=True)
        print("quiz_generation_path=langchain_strict_rag", flush=True)
        print(
            "retrieval_chunking="
            f"recursive chunk_size={settings.rag_chunk_size} chunk_overlap={settings.rag_chunk_overlap}",
            flush=True,
        )
    else:
        for index, corpus_id in enumerate(week.corpus_ids, start=1):
            corpus = repository.get_corpus(corpus_id)
            chunks = repository.get_chunks_for_corpus(corpus_id)
            cleaned_text = " ".join(chunk.text for chunk in chunks)
            print(
                f"[{index}/{len(week.corpus_ids)}] extract candidates start corpus_id={corpus_id} chunks={len(chunks)}",
                flush=True,
            )
            payload = orchestrator.candidate_extractor.extract(
                corpus_id=corpus_id,
                week_id=week.week_id,
                cleaned_text=cleaned_text,
                chunks=chunks,
                progress_callback=lambda message, idx=index, total=len(week.corpus_ids), cid=corpus_id: print(
                    f"[{idx}/{total}] {cid} {message}",
                    flush=True,
                ),
            )
            repository.save_daily_term_candidates(payload)
            print(
                f"[{index}/{len(week.corpus_ids)}] extract candidates done corpus_id={corpus_id} candidates={len(payload.candidates)}",
                flush=True,
            )

    candidate_sets = repository.list_daily_term_candidates_for_week(week.week_id)
    aggregated = aggregate_weekly_candidates(candidate_sets)
    print(
        f"weekly aggregation: week_id={week.week_id} daily_sets={len(candidate_sets)} merged_candidates={len(aggregated)}",
        flush=True,
    )

    if args.seeded_baseline:
        print(
            f"build weekly topics skipped (seed reuse) week_id={week.week_id} topic_axes={len(topic_set.topic_axes)}",
            flush=True,
        )
    else:
        print(f"build weekly topics start week_id={week.week_id}", flush=True)
        topic_set = orchestrator._build_weekly_topic_set(week.week_id)
        repository.save_weekly_topic_set(topic_set)
        print(
            f"build weekly topics done week_id={week.week_id} topic_axes={len(topic_set.topic_axes)}",
            flush=True,
        )

    if args.seeded_baseline:
        print(f"generate weekly guide start week_id={week.week_id}", flush=True)
        guide = orchestrator._generate_weekly_guide(week.week_id)
        repository.save_weekly_guide(guide)
        print(
            f"generate weekly guide done week_id={week.week_id} review_points={len(guide.review_points)}",
            flush=True,
        )

        print(f"generate weekly quiz start week_id={week.week_id}", flush=True)
        quiz = orchestrator._generate_weekly_quiz_set(
            week.week_id,
            num_questions=5,
            progress_callback=lambda message: print(message, flush=True),
        )
        repository.save_weekly_quiz_set(quiz)
        expected_quiz_items = _expected_quiz_items(week.corpus_ids, min_questions_per_corpus=5)
        print(
            f"generate weekly quiz done week_id={week.week_id} items={len(quiz.items)}",
            flush=True,
        )
        print(
            f"quiz_contract_items=true actual={len(quiz.items)} expected={expected_quiz_items}",
            flush=True,
        )

        report = repository.get_weekly_report(week.week_id)
        print(
            f"weekly report ready week_id={week.week_id} question_type_metrics={len(report.question_type_metrics)} topic_coverage={len(report.topic_coverage)}",
            flush=True,
        )
    else:
        print(f"generate weekly guide start week_id={week.week_id}", flush=True)
        guide = orchestrator._generate_weekly_guide(week.week_id)
        repository.save_weekly_guide(guide)
        print(
            f"generate weekly guide done week_id={week.week_id} review_points={len(guide.review_points)}",
            flush=True,
        )

        print(f"generate weekly quiz start week_id={week.week_id}", flush=True)
        quiz = orchestrator._generate_weekly_quiz_set(
            week.week_id,
            num_questions=5,
            progress_callback=lambda message: print(message, flush=True),
        )
        repository.save_weekly_quiz_set(quiz)
        print(
            f"generate weekly quiz done week_id={week.week_id} items={len(quiz.items)}",
            flush=True,
        )

        report = repository.get_weekly_report(week.week_id)
        print(
            f"weekly report ready week_id={week.week_id} question_type_metrics={len(report.question_type_metrics)} topic_coverage={len(report.topic_coverage)}",
            flush=True,
        )

    output_dir = Path("artifacts/pipeline_state")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"weekly_{week.week_id}_topic_set.json").write_text(
        topic_set.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / f"weekly_{week.week_id}_guide.json").write_text(
        guide.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / f"weekly_{week.week_id}_quiz.json").write_text(
        quiz.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / f"weekly_{week.week_id}_report.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    print(f"weekly done: week_id={week.week_id} output_dir={output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
