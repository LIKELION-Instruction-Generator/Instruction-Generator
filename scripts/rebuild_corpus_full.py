from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from uuid import uuid4

from _bootstrap import bootstrap_src_path

bootstrap_src_path()

from stt_quiz_service.config import load_settings
from stt_quiz_service.prompts import read_prompt_section
from stt_quiz_service.orchestrator import WorkflowOrchestrator
from stt_quiz_service.schemas import (
    ChunkDocument,
    CorpusDocument,
    CurriculumRow,
    LectureTargetDocument,
    PipelineIndexRequest,
    PrepareResponse,
    ProcessedLine,
)
from stt_quiz_service.services.ingestion import build_corpus_id, build_lecture_id, chunk_corpus, make_summary
from stt_quiz_service.services.preprocess import sentence_split
from stt_quiz_service.storage.db import build_engine, build_session_factory
from stt_quiz_service.storage.repository import Repository

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
PROGRESS_PATH = Path("artifacts/pipeline_state/rebuild_full_progress.json")


def load_curriculum_rows(curriculum_path: Path) -> list[CurriculumRow]:
    with curriculum_path.open("r", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [
            CurriculumRow(
                week=int(row["week"]),
                date=row["date"],
                session=row["session"],
                time=row["time"],
                subject=row["subject"],
                content=row["content"],
                learning_goal=row["learning_goal"],
                instructor=row["instructor"],
            )
            for row in reader
        ]


def build_run_fingerprint(*, model_name: str, block_chars: int) -> str:
    payload = {
        "preprocess_model": model_name,
        "preprocess_block_chars": block_chars,
        "prompt": read_prompt_section("STT Preprocessing System Prompt"),
    }
    return WorkflowOrchestrator._fingerprint(payload)


def load_progress(*, fingerprint: str) -> dict:
    if not PROGRESS_PATH.exists():
        return {
            "fingerprint": fingerprint,
            "completed_prepare": [],
            "completed_index": [],
            "completed_generate": [],
            "target_ids_by_corpus": {},
            "chunk_count_by_corpus": {},
        }
    data = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
    if data.get("fingerprint") != fingerprint:
        return {
            "fingerprint": fingerprint,
            "completed_prepare": [],
            "completed_index": [],
            "completed_generate": [],
            "target_ids_by_corpus": {},
            "chunk_count_by_corpus": {},
        }
    data.setdefault("completed_prepare", [])
    data.setdefault("completed_index", [])
    data.setdefault("completed_generate", [])
    data.setdefault("target_ids_by_corpus", {})
    data.setdefault("chunk_count_by_corpus", {})
    return data


def save_progress(progress: dict) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


def export_single_corpus(*, output_dir: Path, corpus_doc: CorpusDocument) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for legacy_name in [
        f"{corpus_doc.date}-am.txt",
        f"{corpus_doc.date}-am.json",
        f"{corpus_doc.date}-pm.txt",
        f"{corpus_doc.date}-pm.json",
    ]:
        legacy_path = output_dir / legacy_name
        if legacy_path.exists():
            legacy_path.unlink()
    txt_path = output_dir / f"{corpus_doc.corpus_id}.txt"
    json_path = output_dir / f"{corpus_doc.corpus_id}.json"
    txt_path.write_text(corpus_doc.cleaned_text + "\n", encoding="utf-8")
    json_path.write_text(corpus_doc.model_dump_json(indent=2), encoding="utf-8")


def update_prepare_manifest(
    *,
    output_dir: Path,
    completed_corpus_ids: list[str],
    completed_target_ids: list[str],
    chunks_prepared: int,
) -> None:
    manifest_path = output_dir / "_prepare_manifest.json"
    response = PrepareResponse(
        corpus_version=f"corpus-{uuid4().hex[:12]}",
        corpora_prepared=len(completed_corpus_ids),
        targets_prepared=len(completed_target_ids),
        chunks_prepared=chunks_prepared,
        corpus_ids=completed_corpus_ids,
        target_ids=completed_target_ids,
        output_dir=str(output_dir),
        skipped=False,
    )
    manifest_path.write_text(
        json.dumps({"fingerprint": "manual-rebuild", "response": response.model_dump()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    settings = load_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    repository = Repository(session_factory)
    orchestrator = WorkflowOrchestrator.build(settings, repository)
    orchestrator.bootstrap()
    preprocessor = orchestrator._build_preprocessor(settings)
    run_fingerprint = build_run_fingerprint(
        model_name=preprocessor.model_name,
        block_chars=settings.preprocess_block_chars,
    )
    progress = load_progress(fingerprint=run_fingerprint)

    transcripts_root = settings.transcripts_root
    curriculum_path = settings.curriculum_path
    output_dir = Path("artifacts/preprocessed")

    rows_by_date: dict[str, list[CurriculumRow]] = {}
    for row in load_curriculum_rows(curriculum_path):
        rows_by_date.setdefault(row.date, []).append(row)

    transcript_paths = sorted(transcripts_root.glob("*.txt"))
    print(f"prepare start: files={len(transcript_paths)} model={preprocessor.model_name} block_chars={settings.preprocess_block_chars}", flush=True)
    for idx, transcript_path in enumerate(transcript_paths, start=1):
        match = DATE_RE.search(transcript_path.name)
        if not match:
            continue
        date = match.group(1)
        day_rows = sorted(rows_by_date.get(date, []), key=lambda item: 0 if item.session == "오전" else 1)
        if not day_rows:
            print(f"[{idx}/{len(transcript_paths)}] skip {transcript_path.name}: no curriculum rows", flush=True)
            continue
        corpus_id = build_corpus_id(date)
        if corpus_id in progress["completed_generate"]:
            print(f"[{idx}/{len(transcript_paths)}] skip {date}: already completed", flush=True)
            continue
        raw_text = transcript_path.read_text(encoding="utf-8")
        print(f"[{idx}/{len(transcript_paths)}] preprocess {date} chars={len(raw_text)}", flush=True)
        try:
            if corpus_id not in progress["completed_prepare"]:
                cleaned_text = preprocessor.preprocess_text(
                    raw_text=raw_text,
                    progress_callback=lambda message, outer=idx, total=len(transcript_paths), day=date: print(
                        f"[{outer}/{total}] {day} {message}",
                        flush=True,
                    ),
                )
                processed_lines = [
                    ProcessedLine(
                        text=sentence,
                        practice_example=bool(re.search(r"\bQ\s?\d+\b", sentence, re.IGNORECASE)),
                        source_span=f"{line_idx}:{line_idx}",
                    )
                    for line_idx, sentence in enumerate(sentence_split(cleaned_text))
                ]
                corpus_doc = CorpusDocument(
                    corpus_id=corpus_id,
                    date=date,
                    source_path=str(transcript_path),
                    cleaned_text=cleaned_text,
                    summary=make_summary(cleaned_text),
                    lines=processed_lines,
                )
                chunks = chunk_corpus(corpus_doc)
                target_docs = [
                    LectureTargetDocument(
                        lecture_id=build_lecture_id(row.date, row.session),
                        corpus_id=corpus_id,
                        week=row.week,
                        date=row.date,
                        session=row.session,
                        subject=row.subject,
                        content=row.content,
                        learning_goal=row.learning_goal,
                        instructor=row.instructor,
                        source_path=str(transcript_path),
                        summary=corpus_doc.summary,
                    )
                    for row in day_rows
                ]
                repository.upsert_prepared_corpus([corpus_doc], target_docs, {corpus_id: chunks})
                export_single_corpus(output_dir=output_dir, corpus_doc=corpus_doc)
                progress["completed_prepare"].append(corpus_id)
                progress["target_ids_by_corpus"][corpus_id] = [target.lecture_id for target in target_docs]
                progress["chunk_count_by_corpus"][corpus_id] = len(chunks)
                save_progress(progress)
                print(
                    f"[{idx}/{len(transcript_paths)}] prepare done {date} cleaned_chars={len(cleaned_text)} "
                    f"lines={len(processed_lines)} chunks={len(chunks)}",
                    flush=True,
                )

            if corpus_id not in progress["completed_index"]:
                index_response = orchestrator.build_index(PipelineIndexRequest(corpus_ids=[corpus_id]))
                progress["completed_index"].append(corpus_id)
                save_progress(progress)
                print(
                    f"[{idx}/{len(transcript_paths)}] index done {date} chunks={index_response.chunks_indexed} "
                    f"skipped={index_response.skipped}",
                    flush=True,
                )

            if corpus_id not in progress["completed_generate"]:
                quiz_set, guide, run_log = orchestrator._generate_artifacts(
                    corpus_id=corpus_id,
                    mode="rag",
                    num_questions=5,
                    choice_count=None,
                )
                progress["completed_generate"].append(corpus_id)
                save_progress(progress)
                print(
                    f"[{idx}/{len(transcript_paths)}] generate done {date} run_id={run_log.run_id} "
                    f"questions={len(quiz_set.items)}",
                    flush=True,
                )
        except Exception:
            save_progress(progress)
            raise

    completed_corpus_ids = list(progress["completed_prepare"])
    completed_target_ids = [
        target_id
        for corpus_id in completed_corpus_ids
        for target_id in progress["target_ids_by_corpus"].get(corpus_id, [])
    ]
    completed_chunks = sum(progress["chunk_count_by_corpus"].get(corpus_id, 0) for corpus_id in completed_corpus_ids)
    update_prepare_manifest(
        output_dir=output_dir,
        completed_corpus_ids=completed_corpus_ids,
        completed_target_ids=completed_target_ids,
        chunks_prepared=completed_chunks,
    )
    print(
        f"rebuild done: prepare={len(progress['completed_prepare'])} "
        f"index={len(progress['completed_index'])} generate={len(progress['completed_generate'])}",
        flush=True,
    )


if __name__ == "__main__":
    main()
