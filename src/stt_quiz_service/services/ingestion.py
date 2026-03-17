from __future__ import annotations

import csv
from pathlib import Path
import re
from uuid import uuid4

from stt_quiz_service.schemas import (
    ChunkDocument,
    CorpusDocument,
    CurriculumRow,
    LectureTargetDocument,
    ProcessedLine,
)
from stt_quiz_service.services.preprocess import (
    sentence_split,
)
from stt_quiz_service.services.stt_preprocessor import STTPreprocessor


DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def load_curriculum_rows(curriculum_path: Path) -> list[CurriculumRow]:
    with curriculum_path.open("r", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append(
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
            )
        return rows


def build_lecture_id(date: str, session: str) -> str:
    suffix = "am" if session == "오전" else "pm"
    return f"{date}-{suffix}"


def build_corpus_id(date: str) -> str:
    return date


def make_summary(text: str) -> str:
    sentences = sentence_split(text)
    return " ".join(sentences[:3])[:500]


def chunk_corpus(corpus_doc: CorpusDocument, max_chars: int = 700) -> list[ChunkDocument]:
    chunks: list[ChunkDocument] = []
    buffer: list[str] = []
    start_line = 0
    practice_flag = False
    current_chars = 0
    processed_lines = corpus_doc.lines
    for idx, line in enumerate(processed_lines):
        buffer.append(line.text)
        practice_flag = practice_flag or line.practice_example
        current_chars += len(line.text)
        flush = current_chars >= max_chars or idx == len(processed_lines) - 1
        if flush and buffer:
            chunks.append(
                ChunkDocument(
                    chunk_id=f"{corpus_doc.corpus_id}-{uuid4().hex[:8]}",
                    corpus_id=corpus_doc.corpus_id,
                    chunk_order=len(chunks),
                    text=" ".join(buffer).strip(),
                    source_span=f"{start_line}:{idx}",
                    practice_example=practice_flag,
                    metadata={
                        "date": corpus_doc.date,
                        "practice_example": practice_flag,
                    },
                )
            )
            buffer = []
            current_chars = 0
            start_line = idx + 1
            practice_flag = False
    return chunks


def ingest_transcripts(
    transcripts_root: Path, curriculum_path: Path, preprocessor: STTPreprocessor
) -> tuple[list[CorpusDocument], list[LectureTargetDocument], dict[str, list[ChunkDocument]]]:
    curriculum_rows = load_curriculum_rows(curriculum_path)
    rows_by_date: dict[str, list[CurriculumRow]] = {}
    for row in curriculum_rows:
        rows_by_date.setdefault(row.date, []).append(row)

    corpus_docs: list[CorpusDocument] = []
    target_docs: list[LectureTargetDocument] = []
    chunks_by_corpus: dict[str, list[ChunkDocument]] = {}

    for transcript_path in sorted(transcripts_root.glob("*.txt")):
        match = DATE_RE.search(transcript_path.name)
        if not match:
            continue
        date = match.group(1)
        day_rows = sorted(
            rows_by_date.get(date, []), key=lambda item: 0 if item.session == "오전" else 1
        )
        if not day_rows:
            continue
        raw_text = transcript_path.read_text(encoding="utf-8")
        cleaned_text = preprocessor.preprocess_text(raw_text=raw_text)
        processed_lines = [
            ProcessedLine(
                text=sentence,
                practice_example=bool(re.search(r"\bQ\s?\d+\b", sentence, re.IGNORECASE)),
                source_span=f"{idx}:{idx}",
            )
            for idx, sentence in enumerate(sentence_split(cleaned_text))
        ]
        corpus_id = build_corpus_id(date)
        corpus_doc = CorpusDocument(
            corpus_id=corpus_id,
            date=date,
            source_path=str(transcript_path),
            cleaned_text=cleaned_text,
            summary=make_summary(cleaned_text),
            lines=processed_lines,
        )
        corpus_docs.append(corpus_doc)
        chunks_by_corpus[corpus_id] = chunk_corpus(corpus_doc)
        for row in day_rows:
            lecture_id = build_lecture_id(row.date, row.session)
            target_docs.append(
                LectureTargetDocument(
                    lecture_id=lecture_id,
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
            )
    return corpus_docs, target_docs, chunks_by_corpus
