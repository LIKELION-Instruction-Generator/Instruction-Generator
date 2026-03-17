from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from uuid import uuid4

from sqlalchemy import delete, inspect, select, text
from sqlalchemy import func

from stt_quiz_service.schemas import (
    AuditEvent,
    BundleResponse,
    ChunkDocument,
    CorpusDocument,
    CurriculumRow,
    DailyTermCandidates,
    EvaluationSummary,
    LectureTargetDocument,
    QuizSet,
    RetrievalHit,
    RunLog,
    StudyGuide,
    WeeklyGuide,
    WeeklyQuestionTypeMetric,
    WeeklyQuizSet,
    WeeklyQuizSubmissionDetailResponse,
    WeeklyQuizSubmissionResponse,
    WeeklyQuizReviewResult,
    WeeklyReport,
    WeeklySelection,
    WeeklyTopicCoverage,
    WeeklyTopicSet,
)
from stt_quiz_service.storage.models import (
    Base,
    AuditEventRecord,
    ChunkRecord,
    DailyTermCandidateRecord,
    EmbeddingRecord,
    GenerationRunRecord,
    LectureRecord,
    QuizSetRecord,
    RetrievalHitRecord,
    StudyGuideRecord,
    WeeklyGuideRecord,
    WeeklyQuizSetRecord,
    WeeklyQuizSubmissionAnswerRecord,
    WeeklyQuizSubmissionAttemptRecord,
    WeeklyTopicSetRecord,
)


@dataclass(slots=True)
class CorpusSelection:
    corpus_id: str
    date: str
    subject: str
    content: str
    learning_goal: str
    summary: str
    topic_count: int
    cleaned_text: str = ""


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _norm(values: list[float]) -> float:
    return sqrt(sum(v * v for v in values)) or 1.0


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return _dot(left, right) / (_norm(left) * _norm(right))


class Repository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def create_schema(self) -> None:
        engine = self.session_factory.kw["bind"]
        if engine.dialect.name == "postgresql":
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(engine)
        self._migrate_existing_schema(engine)

    def ensure_vector_search_ready(self, dimension: int) -> None:
        engine = self.session_factory.kw["bind"]
        if engine.dialect.name != "postgresql":
            return
        self._normalize_pgvector_dimension(engine, dimension)
        self._ensure_pgvector_indexes(engine)

    def ping(self) -> None:
        with self.session_factory() as db:
            db.execute(text("select 1"))

    def log_audit_event(
        self,
        *,
        event_type: str,
        status: str,
        actor: str = "system",
        lecture_id: str | None = None,
        run_id: str | None = None,
        details: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            event_type=event_type,
            status=status,
            lecture_id=lecture_id,
            run_id=run_id,
            details=details or {},
        )
        with self.session_factory.begin() as db:
            db.add(
                AuditEventRecord(
                    event_id=event.event_id,
                    created_at=event.created_at,
                    actor=event.actor,
                    event_type=event.event_type,
                    status=event.status,
                    lecture_id=event.lecture_id,
                    run_id=event.run_id,
                    details_json=event.details,
                )
            )
        return event

    def list_audit_events(self, *, limit: int = 100) -> list[AuditEvent]:
        with self.session_factory() as db:
            rows = db.execute(
                select(AuditEventRecord)
                .order_by(AuditEventRecord.created_at.desc())
                .limit(limit)
            ).scalars()
            return [
                AuditEvent(
                    event_id=row.event_id,
                    created_at=row.created_at,
                    actor=row.actor,
                    event_type=row.event_type,
                    status=row.status,
                    lecture_id=row.lecture_id,
                    run_id=row.run_id,
                    details=row.details_json or {},
                )
                for row in rows
            ]

    def upsert_prepared_corpus(
        self,
        corpora: list[CorpusDocument],
        targets: list[LectureTargetDocument],
        chunks_by_corpus: dict[str, list[ChunkDocument]],
    ) -> None:
        corpus_ids = [corpus.corpus_id for corpus in corpora]
        week_ids = sorted({str(target.week) for target in targets})
        primary_target_by_corpus = {
            corpus_id: next(target.lecture_id for target in targets if target.corpus_id == corpus_id)
            for corpus_id in corpus_ids
        }
        with self.session_factory.begin() as db:
            run_ids = db.execute(
                select(GenerationRunRecord.run_id).where(GenerationRunRecord.lecture_id.in_(corpus_ids))
            ).scalars().all()
            if run_ids:
                db.execute(delete(RetrievalHitRecord).where(RetrievalHitRecord.run_id.in_(run_ids)))
                db.execute(delete(QuizSetRecord).where(QuizSetRecord.run_id.in_(run_ids)))
                db.execute(delete(StudyGuideRecord).where(StudyGuideRecord.run_id.in_(run_ids)))
                db.execute(delete(GenerationRunRecord).where(GenerationRunRecord.run_id.in_(run_ids)))

            chunk_ids = db.execute(
                select(ChunkRecord.chunk_id).where(ChunkRecord.corpus_id.in_(corpus_ids))
            ).scalars().all()
            if chunk_ids:
                db.execute(delete(EmbeddingRecord).where(EmbeddingRecord.chunk_id.in_(chunk_ids)))

            db.execute(delete(ChunkRecord).where(ChunkRecord.corpus_id.in_(corpus_ids)))
            db.execute(delete(DailyTermCandidateRecord).where(DailyTermCandidateRecord.corpus_id.in_(corpus_ids)))
            if week_ids:
                db.execute(delete(WeeklyTopicSetRecord).where(WeeklyTopicSetRecord.week_id.in_(week_ids)))
                db.execute(delete(WeeklyGuideRecord).where(WeeklyGuideRecord.week_id.in_(week_ids)))
                db.execute(delete(WeeklyQuizSetRecord).where(WeeklyQuizSetRecord.week_id.in_(week_ids)))
            db.execute(delete(LectureRecord).where(LectureRecord.corpus_id.in_(corpus_ids)))

            for target in targets:
                db.merge(
                    LectureRecord(
                        lecture_id=target.lecture_id,
                        corpus_id=target.corpus_id,
                        week=target.week,
                        date=target.date,
                        session=target.session,
                        subject=target.subject,
                        content=target.content,
                        learning_goal=target.learning_goal,
                        source_path=target.source_path,
                        cleaned_text=next(
                            corpus.cleaned_text for corpus in corpora if corpus.corpus_id == target.corpus_id
                        ),
                        summary=target.summary,
                    )
                )
            for corpus_id, chunks in chunks_by_corpus.items():
                for chunk_doc in chunks:
                    chunk = ChunkRecord(
                        chunk_id=chunk_doc.chunk_id,
                        corpus_id=chunk_doc.corpus_id,
                        lecture_id=primary_target_by_corpus[corpus_id],
                        session="",
                        chunk_order=chunk_doc.chunk_order,
                        text=chunk_doc.text,
                        source_span=chunk_doc.source_span,
                        practice_example=chunk_doc.practice_example,
                        metadata_json=chunk_doc.metadata,
                    )
                    db.add(chunk)

    def upsert_embeddings(
        self,
        embeddings: dict[str, list[float]],
        *,
        provider: str,
        dimension: int,
    ) -> None:
        with self.session_factory.begin() as db:
            for chunk_id, vector in embeddings.items():
                db.merge(
                    EmbeddingRecord(
                        chunk_id=chunk_id,
                        vector=vector,
                        provider=provider,
                        dimension=dimension,
                    )
                )

    def list_corpora(self) -> list[CorpusSelection]:
        with self.session_factory() as db:
            rows = db.execute(
                select(LectureRecord).order_by(LectureRecord.date, LectureRecord.session)
            ).scalars()
            grouped: dict[str, list[LectureRecord]] = {}
            for row in rows:
                grouped.setdefault(row.corpus_id, []).append(row)
            selections: list[CorpusSelection] = []
            for corpus_id, group in grouped.items():
                contents = list(dict.fromkeys(row.content for row in group if row.content))
                goals = list(dict.fromkeys(row.learning_goal for row in group if row.learning_goal))
                subjects = list(dict.fromkeys(row.subject for row in group if row.subject))
                selections.append(
                    CorpusSelection(
                        corpus_id=corpus_id,
                        date=group[0].date,
                        subject=" / ".join(subjects),
                        content=" / ".join(contents),
                        learning_goal=" / ".join(goals),
                        summary=group[0].summary,
                        topic_count=len(group),
                        cleaned_text=group[0].cleaned_text,
                    )
                )
            return sorted(selections, key=lambda item: item.date)

    @staticmethod
    def _load_ready_week_ids(db) -> set[str]:
        topic_ids = set(db.execute(select(WeeklyTopicSetRecord.week_id)).scalars().all())
        guide_ids = set(db.execute(select(WeeklyGuideRecord.week_id)).scalars().all())
        quiz_ids = set(db.execute(select(WeeklyQuizSetRecord.week_id)).scalars().all())
        return topic_ids & guide_ids & quiz_ids

    def list_weeks(self, *, ready_only: bool = False) -> list[WeeklySelection]:
        with self.session_factory() as db:
            ready_week_ids = self._load_ready_week_ids(db) if ready_only else None
            rows = db.execute(
                select(LectureRecord)
                .where(LectureRecord.week > 0)
                .order_by(LectureRecord.week, LectureRecord.date, LectureRecord.session)
            ).scalars()
            grouped: dict[int, list[LectureRecord]] = {}
            for row in rows:
                grouped.setdefault(row.week, []).append(row)
            selections: list[WeeklySelection] = []
            for week, group in grouped.items():
                if ready_week_ids is not None and str(week) not in ready_week_ids:
                    continue
                selections.append(
                    WeeklySelection(
                        week_id=str(week),
                        week=week,
                        corpus_ids=sorted({row.corpus_id for row in group}),
                        dates=sorted({row.date for row in group}),
                        subject=" / ".join(dict.fromkeys(row.subject for row in group if row.subject)),
                        content=" / ".join(dict.fromkeys(row.content for row in group if row.content)),
                        learning_goal=" / ".join(
                            dict.fromkeys(row.learning_goal for row in group if row.learning_goal)
                        ),
                    )
                )
            return sorted(selections, key=lambda item: item.week)

    def backfill_lecture_weeks(self, curriculum_rows: list[CurriculumRow]) -> None:
        week_by_lecture_id = {
            f"{row.date}-{'am' if row.session == '오전' else 'pm'}": row.week
            for row in curriculum_rows
        }
        if not week_by_lecture_id:
            return
        with self.session_factory.begin() as db:
            rows = db.execute(select(LectureRecord)).scalars().all()
            for row in rows:
                week = week_by_lecture_id.get(row.lecture_id)
                if week is None or row.week == week:
                    continue
                row.week = week

    def get_week(self, week_id: str) -> WeeklySelection:
        weeks = {week.week_id: week for week in self.list_weeks()}
        if week_id not in weeks:
            raise KeyError(f"Unknown week_id: {week_id}")
        return weeks[week_id]

    def get_corpus(self, corpus_id: str) -> CorpusSelection:
        with self.session_factory() as db:
            rows = db.execute(
                select(LectureRecord)
                .where(LectureRecord.corpus_id == corpus_id)
                .order_by(LectureRecord.date, LectureRecord.session)
            ).scalars().all()
            if not rows:
                raise KeyError(f"Unknown corpus_id: {corpus_id}")
            contents = list(dict.fromkeys(row.content for row in rows if row.content))
            goals = list(dict.fromkeys(row.learning_goal for row in rows if row.learning_goal))
            subjects = list(dict.fromkeys(row.subject for row in rows if row.subject))
            return CorpusSelection(
                corpus_id=corpus_id,
                date=rows[0].date,
                subject=" / ".join(subjects),
                content=" / ".join(contents),
                learning_goal=" / ".join(goals),
                summary=rows[0].summary,
                topic_count=len(rows),
                cleaned_text=rows[0].cleaned_text,
            )

    def get_week_chunks(self, week_id: str) -> list[ChunkDocument]:
        week = self.get_week(week_id)
        return self.get_all_chunks(week.corpus_ids)

    def get_chunks_for_corpus(self, corpus_id: str) -> list[ChunkDocument]:
        return self.get_chunks_by_corpus(corpus_id)

    def get_chunks_by_corpus(self, corpus_id: str) -> list[ChunkDocument]:
        with self.session_factory() as db:
            rows = db.execute(
                select(ChunkRecord)
                .where(ChunkRecord.corpus_id == corpus_id)
                .order_by(ChunkRecord.chunk_order)
            ).scalars()
            return [
                ChunkDocument(
                    chunk_id=row.chunk_id,
                    corpus_id=row.corpus_id,
                    chunk_order=row.chunk_order,
                    text=row.text,
                    source_span=row.source_span,
                    practice_example=row.practice_example,
                    metadata=row.metadata_json or {},
                )
                for row in rows
            ]

    def list_corpus_ids(self) -> list[str]:
        with self.session_factory() as db:
            rows = db.execute(
                select(LectureRecord.corpus_id).distinct().order_by(LectureRecord.corpus_id)
            ).all()
            return [row[0] for row in rows]

    def list_target_ids(self, corpus_ids: list[str] | None = None) -> list[str]:
        with self.session_factory() as db:
            statement = select(LectureRecord.lecture_id).order_by(LectureRecord.date, LectureRecord.session)
            if corpus_ids:
                statement = statement.where(LectureRecord.corpus_id.in_(corpus_ids))
            rows = db.execute(statement).all()
            return [row[0] for row in rows]

    def count_chunks(self, corpus_ids: list[str] | None = None) -> int:
        with self.session_factory() as db:
            statement = select(func.count(ChunkRecord.chunk_id))
            if corpus_ids:
                statement = statement.where(ChunkRecord.corpus_id.in_(corpus_ids))
            return int(db.execute(statement).scalar_one() or 0)

    def get_embedding_dimension(self, provider: str | None = None) -> int | None:
        with self.session_factory() as db:
            statement = select(EmbeddingRecord.dimension)
            if provider:
                statement = statement.where(EmbeddingRecord.provider == provider)
            statement = statement.limit(1)
            value = db.execute(statement).scalar_one_or_none()
            return int(value) if value is not None else None

    def get_all_chunks(self, corpus_ids: list[str] | None = None) -> list[ChunkDocument]:
        with self.session_factory() as db:
            statement = select(ChunkRecord).order_by(ChunkRecord.corpus_id, ChunkRecord.chunk_order)
            if corpus_ids:
                statement = statement.where(ChunkRecord.corpus_id.in_(corpus_ids))
            rows = db.execute(statement).scalars()
            return [
                ChunkDocument(
                    chunk_id=row.chunk_id,
                    corpus_id=row.corpus_id,
                    chunk_order=row.chunk_order,
                    text=row.text,
                    source_span=row.source_span,
                    practice_example=row.practice_example,
                    metadata=row.metadata_json or {},
                )
                for row in rows
            ]

    def has_embeddings_for_corpora(
        self,
        corpus_ids: list[str],
        *,
        provider: str,
    ) -> bool:
        if not corpus_ids:
            return False
        with self.session_factory() as db:
            chunk_count = db.execute(
                select(func.count(ChunkRecord.chunk_id)).where(ChunkRecord.corpus_id.in_(corpus_ids))
            ).scalar_one()
            embedding_count = db.execute(
                select(func.count(EmbeddingRecord.chunk_id))
                .join(ChunkRecord, ChunkRecord.chunk_id == EmbeddingRecord.chunk_id)
                .where(ChunkRecord.corpus_id.in_(corpus_ids))
                .where(EmbeddingRecord.provider == provider)
            ).scalar_one()
            return chunk_count > 0 and embedding_count == chunk_count

    def latest_bundle_exists(self, corpus_id: str) -> bool:
        with self.session_factory() as db:
            run_row = db.execute(
                select(GenerationRunRecord.run_id)
                .where(GenerationRunRecord.lecture_id == corpus_id)
                .order_by(GenerationRunRecord.created_at.desc(), GenerationRunRecord.run_id.desc())
                .limit(1)
            ).scalar_one_or_none()
            return run_row is not None

    def search_chunks(
        self,
        corpus_id: str,
        query_vector: list[float],
        *,
        top_k: int,
        exclude_practice: bool,
    ) -> list[RetrievalHit]:
        with self.session_factory() as db:
            if db.bind.dialect.name == "postgresql":
                distance_expr = EmbeddingRecord.vector.cosine_distance(query_vector)
                statement = (
                    select(ChunkRecord, distance_expr.label("distance"))
                    .join(EmbeddingRecord, EmbeddingRecord.chunk_id == ChunkRecord.chunk_id)
                    .where(ChunkRecord.corpus_id == corpus_id)
                    .order_by(distance_expr)
                    .limit(top_k)
                )
                if exclude_practice:
                    statement = statement.where(ChunkRecord.practice_example.is_(False))
                rows = db.execute(statement).all()
                hits: list[RetrievalHit] = []
                for rank, (chunk_row, distance) in enumerate(rows, start=1):
                    hits.append(
                        RetrievalHit(
                            chunk_id=chunk_row.chunk_id,
                            corpus_id=chunk_row.corpus_id,
                            chunk_order=chunk_row.chunk_order,
                            text=chunk_row.text,
                            source_span=chunk_row.source_span,
                            practice_example=chunk_row.practice_example,
                            metadata=chunk_row.metadata_json or {},
                            rank=rank,
                            score=max(0.0, 1.0 - float(distance or 0.0)),
                        )
                    )
                return hits

            rows = db.execute(
                select(ChunkRecord, EmbeddingRecord)
                .join(EmbeddingRecord, EmbeddingRecord.chunk_id == ChunkRecord.chunk_id)
                .where(ChunkRecord.corpus_id == corpus_id)
            ).all()
            scored: list[tuple[float, RetrievalHit]] = []
            for chunk_row, embedding_row in rows:
                if exclude_practice and chunk_row.practice_example:
                    continue
                score = cosine_similarity(query_vector, embedding_row.vector)
                scored.append(
                    (
                        score,
                        RetrievalHit(
                            chunk_id=chunk_row.chunk_id,
                            corpus_id=chunk_row.corpus_id,
                            chunk_order=chunk_row.chunk_order,
                            text=chunk_row.text,
                            source_span=chunk_row.source_span,
                            practice_example=chunk_row.practice_example,
                            metadata=chunk_row.metadata_json or {},
                            rank=0,
                            score=score,
                        ),
                    )
                )
            ordered = sorted(scored, key=lambda x: x[0], reverse=True)[:top_k]
            return [
                hit.model_copy(update={"rank": rank})
                for rank, (_, hit) in enumerate(ordered, start=1)
            ]

    def save_bundle(
        self,
        *,
        corpus_id: str,
        mode: str,
        model_name: str,
        retrieval_query: str,
        retrieved_chunk_ids: list[str],
        retrieval_hits: list[RetrievalHit],
        retrieval_top_k: int,
        embedder_provider: str,
        profile_distribution: dict[str, int],
        latency_ms: int,
        token_usage: int,
        evaluation: EvaluationSummary,
        quiz_set: QuizSet,
        study_guide: StudyGuide,
    ) -> RunLog:
        run_id = uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        run_log = RunLog(
            run_id=run_id,
            corpus_id=corpus_id,
            mode=mode,
            retrieval_query=retrieval_query,
            retrieved_chunk_ids=retrieved_chunk_ids,
            retrieval_hits=retrieval_hits,
            retrieval_top_k=retrieval_top_k,
            embedder_provider=embedder_provider,
            profile_distribution=profile_distribution,
            latency_ms=latency_ms,
            token_usage=token_usage,
            model_name=model_name,
            evaluation=evaluation,
        )
        with self.session_factory.begin() as db:
            db.add(
                GenerationRunRecord(
                    run_id=run_id,
                    created_at=created_at,
                    lecture_id=corpus_id,
                    mode=mode,
                    retrieval_query=retrieval_query,
                    retrieved_chunk_ids=retrieved_chunk_ids,
                    retrieval_top_k=retrieval_top_k,
                    embedder_provider=embedder_provider,
                    latency_ms=latency_ms,
                    token_usage=token_usage,
                    model_name=model_name,
                    evaluation_json=evaluation.model_dump(),
                )
            )
            db.add(
                QuizSetRecord(
                    run_id=run_id,
                    lecture_id=corpus_id,
                    payload=quiz_set.model_dump(),
                )
            )
            db.add(
                StudyGuideRecord(
                    run_id=run_id,
                    lecture_id=corpus_id,
                    payload=study_guide.model_dump(),
                )
            )
            for hit in retrieval_hits:
                db.add(
                    RetrievalHitRecord(
                        run_id=run_id,
                        lecture_id=corpus_id,
                        corpus_id=hit.corpus_id,
                        chunk_id=hit.chunk_id,
                        session="",
                        chunk_order=hit.chunk_order,
                        rank=hit.rank,
                        score=hit.score,
                        text_snapshot=hit.text,
                        source_span=hit.source_span,
                        practice_example=hit.practice_example,
                        metadata_json=hit.metadata,
                    )
                )
        return run_log

    def get_run(self, run_id: str) -> RunLog:
        with self.session_factory() as db:
            row = db.get(GenerationRunRecord, run_id)
            if row is None:
                raise KeyError(f"Unknown run_id: {run_id}")
            evaluation = (
                EvaluationSummary.model_validate(row.evaluation_json)
                if row.evaluation_json
                else None
            )
            return RunLog(
                run_id=row.run_id,
                corpus_id=row.lecture_id,
                mode=row.mode,
                retrieval_query=row.retrieval_query or "",
                retrieved_chunk_ids=row.retrieved_chunk_ids or [],
                retrieval_hits=self._load_retrieval_hits(db, row.run_id),
                retrieval_top_k=row.retrieval_top_k or 0,
                embedder_provider=row.embedder_provider or "",
                profile_distribution=self._load_profile_distribution(db, row.run_id),
                latency_ms=row.latency_ms,
                token_usage=row.token_usage,
                model_name=row.model_name,
                evaluation=evaluation,
            )

    @staticmethod
    def _load_profile_distribution(db, run_id: str) -> dict[str, int]:
        quiz_row = db.get(QuizSetRecord, run_id)
        if not quiz_row or not quiz_row.payload:
            return {}
        items = quiz_row.payload.get("items", [])
        counter: dict[str, int] = {}
        for item in items:
            profile = item.get("question_profile")
            if not profile:
                continue
            counter[profile] = counter.get(profile, 0) + 1
        return counter

    @staticmethod
    def _load_retrieval_hits(db, run_id: str) -> list[RetrievalHit]:
        rows = db.execute(
            select(RetrievalHitRecord)
            .where(RetrievalHitRecord.run_id == run_id)
            .order_by(RetrievalHitRecord.rank)
        ).scalars()
        return [
            RetrievalHit(
                chunk_id=row.chunk_id,
                corpus_id=row.corpus_id,
                chunk_order=row.chunk_order,
                text=row.text_snapshot,
                source_span=row.source_span,
                practice_example=row.practice_example,
                metadata=row.metadata_json or {},
                rank=row.rank,
                score=row.score,
            )
            for row in rows
        ]

    @staticmethod
    def _migrate_existing_schema(engine) -> None:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if "lectures" in table_names:
            Repository._ensure_lecture_columns(engine, inspector)
        if "chunks" in table_names:
            Repository._ensure_chunk_columns(engine, inspector)
            if engine.dialect.name == "postgresql":
                Repository._drop_legacy_chunk_lecture_fk(engine)
        if "retrieval_hits" in table_names:
            Repository._ensure_retrieval_hit_columns(engine, inspector)
        if "generation_runs" in table_names:
            Repository._ensure_generation_run_columns(engine, inspector)
        if engine.dialect.name == "postgresql" and "embeddings" in table_names:
            Repository._migrate_embedding_vector_column(engine)
            dimension = Repository._discover_embedding_dimension(engine)
            if dimension is not None:
                Repository._normalize_pgvector_dimension(engine, dimension)
                Repository._ensure_pgvector_indexes(engine)

    @staticmethod
    def _ensure_generation_run_columns(engine, inspector) -> None:
        existing_columns = {column["name"] for column in inspector.get_columns("generation_runs")}
        statements: list[str] = []
        if "created_at" not in existing_columns:
            statements.append("ALTER TABLE generation_runs ADD COLUMN created_at VARCHAR(64) NOT NULL DEFAULT ''")
        if "retrieval_query" not in existing_columns:
            statements.append("ALTER TABLE generation_runs ADD COLUMN retrieval_query TEXT NOT NULL DEFAULT ''")
        if "retrieval_top_k" not in existing_columns:
            statements.append("ALTER TABLE generation_runs ADD COLUMN retrieval_top_k INTEGER NOT NULL DEFAULT 0")
        if "embedder_provider" not in existing_columns:
            statements.append("ALTER TABLE generation_runs ADD COLUMN embedder_provider VARCHAR(64) NOT NULL DEFAULT ''")
        if not statements:
            return
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
            if "created_at" not in existing_columns:
                conn.execute(
                    text(
                        "UPDATE generation_runs SET created_at = COALESCE(NULLIF(created_at, ''), CURRENT_TIMESTAMP::text)"
                        if engine.dialect.name == "postgresql"
                        else "UPDATE generation_runs SET created_at = COALESCE(NULLIF(created_at, ''), CURRENT_TIMESTAMP)"
                    )
                )

    @staticmethod
    def _ensure_lecture_columns(engine, inspector) -> None:
        existing_columns = {column["name"] for column in inspector.get_columns("lectures")}
        statements: list[str] = []
        if "corpus_id" not in existing_columns:
            statements.append("ALTER TABLE lectures ADD COLUMN corpus_id VARCHAR(128) NOT NULL DEFAULT ''")
        if "week" not in existing_columns:
            statements.append("ALTER TABLE lectures ADD COLUMN week INTEGER NOT NULL DEFAULT 0")
        if not statements:
            return
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
            if "corpus_id" not in existing_columns and {"date", "session"} <= existing_columns:
                if engine.dialect.name == "postgresql":
                    conn.execute(
                        text(
                            """
                            UPDATE lectures
                            SET corpus_id = CASE
                                WHEN date IS NOT NULL AND date <> '' THEN date
                                ELSE split_part(lecture_id, '-', 1) || '-' || split_part(lecture_id, '-', 2) || '-' || split_part(lecture_id, '-', 3)
                            END
                            """
                        )
                    )
                else:
                    conn.execute(
                        text(
                            """
                            UPDATE lectures
                            SET corpus_id = CASE
                                WHEN date IS NOT NULL AND date <> '' THEN date
                                ELSE substr(lecture_id, 1, 10)
                            END
                            """
                        )
                    )

    @staticmethod
    def _ensure_chunk_columns(engine, inspector) -> None:
        existing_columns = {column["name"] for column in inspector.get_columns("chunks")}
        if "corpus_id" in existing_columns:
            return
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE chunks ADD COLUMN corpus_id VARCHAR(128) NOT NULL DEFAULT ''"))
            if "lecture_id" in existing_columns:
                if engine.dialect.name == "postgresql":
                    conn.execute(
                        text(
                            """
                            UPDATE chunks
                            SET corpus_id = CASE
                                WHEN lecture_id IS NOT NULL AND lecture_id <> '' THEN split_part(lecture_id, '-', 1) || '-' || split_part(lecture_id, '-', 2) || '-' || split_part(lecture_id, '-', 3)
                                ELSE corpus_id
                            END
                            """
                        )
                    )
                else:
                    conn.execute(
                        text(
                            """
                            UPDATE chunks
                            SET corpus_id = CASE
                                WHEN lecture_id IS NOT NULL AND lecture_id <> '' THEN substr(lecture_id, 1, 10)
                                ELSE corpus_id
                            END
                            """
                        )
                    )

    @staticmethod
    def _drop_legacy_chunk_lecture_fk(engine) -> None:
        query = text(
            """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'chunks'
              AND constraint_type = 'FOREIGN KEY'
            """
        )
        with engine.begin() as conn:
            names = [row[0] for row in conn.execute(query).all()]
            for name in names:
                conn.execute(text(f'ALTER TABLE chunks DROP CONSTRAINT IF EXISTS "{name}"'))

    @staticmethod
    def _ensure_retrieval_hit_columns(engine, inspector) -> None:
        existing_columns = {column["name"] for column in inspector.get_columns("retrieval_hits")}
        if "corpus_id" in existing_columns:
            return
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE retrieval_hits ADD COLUMN corpus_id VARCHAR(128) NOT NULL DEFAULT ''"))
            if "lecture_id" in existing_columns:
                if engine.dialect.name == "postgresql":
                    conn.execute(
                        text(
                            """
                            UPDATE retrieval_hits
                            SET corpus_id = CASE
                                WHEN lecture_id IS NOT NULL AND lecture_id <> '' THEN split_part(lecture_id, '-', 1) || '-' || split_part(lecture_id, '-', 2) || '-' || split_part(lecture_id, '-', 3)
                                ELSE corpus_id
                            END
                            """
                        )
                    )
                else:
                    conn.execute(
                        text(
                            """
                            UPDATE retrieval_hits
                            SET corpus_id = CASE
                                WHEN lecture_id IS NOT NULL AND lecture_id <> '' THEN substr(lecture_id, 1, 10)
                                ELSE corpus_id
                            END
                            """
                        )
                    )

    def get_latest_bundle(self, corpus_id: str) -> BundleResponse:
        with self.session_factory() as db:
            run_row = db.execute(
                select(GenerationRunRecord)
                .where(GenerationRunRecord.lecture_id == corpus_id)
                .order_by(GenerationRunRecord.created_at.desc(), GenerationRunRecord.run_id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if run_row is None:
                raise KeyError(f"No generated bundle found for corpus_id: {corpus_id}")
            quiz_row = db.get(QuizSetRecord, run_row.run_id)
            guide_row = db.get(StudyGuideRecord, run_row.run_id)
            if quiz_row is None or guide_row is None:
                raise KeyError(f"Incomplete generated bundle for corpus_id: {corpus_id}")
            evaluation = (
                EvaluationSummary.model_validate(run_row.evaluation_json)
                if run_row.evaluation_json
                else None
            )
            run = RunLog(
                run_id=run_row.run_id,
                corpus_id=run_row.lecture_id,
                mode=run_row.mode,
                retrieval_query=run_row.retrieval_query or "",
                retrieved_chunk_ids=run_row.retrieved_chunk_ids or [],
                retrieval_hits=self._load_retrieval_hits(db, run_row.run_id),
                retrieval_top_k=run_row.retrieval_top_k or 0,
                embedder_provider=run_row.embedder_provider or "",
                profile_distribution=self._load_profile_distribution(db, run_row.run_id),
                latency_ms=run_row.latency_ms,
                token_usage=run_row.token_usage,
                model_name=run_row.model_name,
                evaluation=evaluation,
            )
            return BundleResponse(
                run=run,
                quiz_set=QuizSet.model_validate(quiz_row.payload),
                study_guide=StudyGuide.model_validate(guide_row.payload),
            )

    def save_daily_term_candidates(self, payload: DailyTermCandidates) -> None:
        with self.session_factory.begin() as db:
            db.merge(
                DailyTermCandidateRecord(
                    corpus_id=payload.corpus_id,
                    week_id=payload.week_id,
                    payload=payload.model_dump(),
                )
            )

    def get_daily_term_candidates(self, corpus_id: str) -> DailyTermCandidates:
        with self.session_factory() as db:
            row = db.get(DailyTermCandidateRecord, corpus_id)
            if row is None:
                raise KeyError(f"No daily term candidates found for corpus_id: {corpus_id}")
            return DailyTermCandidates.model_validate(row.payload)

    def list_daily_term_candidates_for_week(self, week_id: str) -> list[DailyTermCandidates]:
        with self.session_factory() as db:
            rows = db.execute(
                select(DailyTermCandidateRecord)
                .where(DailyTermCandidateRecord.week_id == week_id)
                .order_by(DailyTermCandidateRecord.corpus_id)
            ).scalars()
            return [DailyTermCandidates.model_validate(row.payload) for row in rows]

    def save_weekly_topic_set(self, payload: WeeklyTopicSet) -> None:
        with self.session_factory.begin() as db:
            db.merge(
                WeeklyTopicSetRecord(
                    week_id=payload.week_id,
                    payload=payload.model_dump(),
                )
            )

    def get_weekly_topic_set(self, week_id: str) -> WeeklyTopicSet:
        with self.session_factory() as db:
            row = db.get(WeeklyTopicSetRecord, week_id)
            if row is None:
                raise KeyError(f"No weekly topic set found for week_id: {week_id}")
            return WeeklyTopicSet.model_validate(row.payload)

    def save_weekly_guide(self, payload: WeeklyGuide) -> None:
        with self.session_factory.begin() as db:
            db.merge(
                WeeklyGuideRecord(
                    week_id=payload.week_id,
                    payload=payload.model_dump(),
                )
            )

    def get_weekly_guide(self, week_id: str) -> WeeklyGuide:
        with self.session_factory() as db:
            row = db.get(WeeklyGuideRecord, week_id)
            if row is None:
                raise KeyError(f"No weekly guide found for week_id: {week_id}")
            return WeeklyGuide.model_validate(row.payload)

    def save_weekly_quiz_set(self, payload: WeeklyQuizSet) -> None:
        with self.session_factory.begin() as db:
            db.merge(
                WeeklyQuizSetRecord(
                    week_id=payload.week_id,
                    payload=payload.model_dump(),
                )
            )

    def get_weekly_quiz_set(self, week_id: str) -> WeeklyQuizSet:
        with self.session_factory() as db:
            row = db.get(WeeklyQuizSetRecord, week_id)
            if row is None:
                raise KeyError(f"No weekly quiz set found for week_id: {week_id}")
            return WeeklyQuizSet.model_validate(row.payload)

    def save_weekly_quiz_submission(self, payload: WeeklyQuizSubmissionResponse) -> None:
        with self.session_factory.begin() as db:
            db.add(
                WeeklyQuizSubmissionAttemptRecord(
                    attempt_id=payload.attempt_id,
                    week_id=payload.week_id,
                    submitted_at=payload.submitted_at,
                    total_questions=payload.total_questions,
                    correct_count=payload.correct_count,
                    score=payload.score,
                )
            )
            db.flush()
            for question_order, result in enumerate(payload.results):
                db.add(
                    WeeklyQuizSubmissionAnswerRecord(
                        attempt_id=payload.attempt_id,
                        item_id=result.item_id,
                        question_order=question_order,
                        selected_option_index=result.selected_option_index,
                        correct_option_index=result.correct_option_index,
                        is_correct=result.is_correct,
                    )
                )

    def get_latest_weekly_quiz_submission(self, week_id: str) -> WeeklyQuizSubmissionDetailResponse:
        with self.session_factory() as db:
            attempt = db.execute(
                select(WeeklyQuizSubmissionAttemptRecord)
                .where(WeeklyQuizSubmissionAttemptRecord.week_id == week_id)
                .order_by(
                    WeeklyQuizSubmissionAttemptRecord.submitted_at.desc(),
                    WeeklyQuizSubmissionAttemptRecord.attempt_id.desc(),
                )
                .limit(1)
            ).scalar_one_or_none()
            if attempt is None:
                raise KeyError(f"No weekly quiz submission found for week_id: {week_id}")
            return self._build_weekly_quiz_submission_detail(db, attempt)

    def get_weekly_quiz_submission_attempt(
        self,
        week_id: str,
        attempt_id: str,
    ) -> WeeklyQuizSubmissionDetailResponse:
        with self.session_factory() as db:
            attempt = db.get(WeeklyQuizSubmissionAttemptRecord, attempt_id)
            if attempt is None:
                raise KeyError(f"Unknown weekly quiz attempt_id: {attempt_id}")
            if attempt.week_id != week_id:
                raise KeyError(f"attempt_id {attempt_id} does not belong to week_id: {week_id}")
            return self._build_weekly_quiz_submission_detail(db, attempt)

    @staticmethod
    def _build_weekly_quiz_submission_detail(
        db,
        attempt: WeeklyQuizSubmissionAttemptRecord,
    ) -> WeeklyQuizSubmissionDetailResponse:
        quiz_row = db.get(WeeklyQuizSetRecord, attempt.week_id)
        if quiz_row is None:
            raise KeyError(f"No weekly quiz set found for week_id: {attempt.week_id}")
        quiz_set = WeeklyQuizSet.model_validate(quiz_row.payload)
        item_by_id = {item.item_id: item for item in quiz_set.items}
        answer_rows = db.execute(
            select(WeeklyQuizSubmissionAnswerRecord)
            .where(WeeklyQuizSubmissionAnswerRecord.attempt_id == attempt.attempt_id)
            .order_by(WeeklyQuizSubmissionAnswerRecord.question_order)
        ).scalars().all()
        results: list[WeeklyQuizReviewResult] = []
        for row in answer_rows:
            item = item_by_id.get(row.item_id)
            if item is None:
                raise KeyError(
                    f"Stored weekly quiz submission references unknown item_id={row.item_id} "
                    f"for week_id={attempt.week_id}"
                )
            results.append(
                WeeklyQuizReviewResult(
                    item_id=item.item_id,
                    question=item.question,
                    options=item.options,
                    selected_option_index=row.selected_option_index,
                    correct_option_index=row.correct_option_index,
                    answer_text=item.answer_text,
                    explanation=item.explanation,
                    is_correct=row.is_correct,
                    topic_axis_label=item.topic_axis_label,
                    source_corpus_id=item.source_corpus_id,
                    source_date=item.source_date,
                    learning_goal=item.learning_goal,
                    learning_goal_source=item.learning_goal_source,
                    retrieved_chunk_ids=item.retrieved_chunk_ids,
                    evidence_chunk_ids=item.evidence_chunk_ids,
                )
            )
        return WeeklyQuizSubmissionDetailResponse(
            attempt_id=attempt.attempt_id,
            week_id=attempt.week_id,
            total_questions=attempt.total_questions,
            correct_count=attempt.correct_count,
            score=attempt.score,
            submitted_at=attempt.submitted_at,
            results=results,
        )

    def get_weekly_report(self, week_id: str) -> WeeklyReport:
        topic_set = self.get_weekly_topic_set(week_id)
        quiz_set = self.get_weekly_quiz_set(week_id)
        axis_by_label = {axis.label: axis for axis in topic_set.topic_axes}
        profile_to_topics: dict[str, set[str]] = {}
        mismatched_axis_item_count = 0
        for item in quiz_set.items:
            axis = axis_by_label.get(item.topic_axis_label)
            if axis is None or item.source_corpus_id not in axis.source_corpus_ids:
                mismatched_axis_item_count += 1
                continue
            profile_to_topics.setdefault(item.question_profile, set()).add(item.topic_axis_label)
        question_type_metrics = [
            WeeklyQuestionTypeMetric(
                question_profile=profile,
                question_count=sum(1 for item in quiz_set.items if item.question_profile == profile),
                covered_topic_axes=sorted(profile_to_topics.get(profile, set())),
            )
            for profile in sorted({item.question_profile for item in quiz_set.items})
        ]
        topic_coverage = [
            WeeklyTopicCoverage(
                topic_axis_label=axis.label,
                question_count=sum(
                    1
                    for item in quiz_set.items
                    if item.topic_axis_label == axis.label and item.source_corpus_id in axis.source_corpus_ids
                ),
                supporting_terms=axis.supporting_terms,
            )
            for axis in topic_set.topic_axes
        ]
        learning_goal_source_distribution: dict[str, int] = {}
        for item in quiz_set.items:
            learning_goal_source_distribution[item.learning_goal_source] = (
                learning_goal_source_distribution.get(item.learning_goal_source, 0) + 1
            )
        notes = ["학습자 응답 데이터가 없어 문항 유형별 커버리지 기준으로 리포트를 구성했습니다."]
        if mismatched_axis_item_count:
            notes.append(f"topic axis/source mismatch items={mismatched_axis_item_count}")
        return WeeklyReport(
            week_id=week_id,
            question_type_metrics=question_type_metrics,
            topic_coverage=topic_coverage,
            mismatched_axis_item_count=mismatched_axis_item_count,
            learning_goal_source_distribution=learning_goal_source_distribution,
            notes=notes,
        )

    @staticmethod
    def _migrate_embedding_vector_column(engine) -> None:
        with engine.begin() as conn:
            udt_name = conn.execute(
                text(
                    """
                    SELECT udt_name
                    FROM information_schema.columns
                    WHERE table_name = 'embeddings' AND column_name = 'vector'
                    """
                )
            ).scalar_one_or_none()
            if udt_name == "vector":
                return

            existing_columns = {
                row[0]
                for row in conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'embeddings'
                        """
                    )
                ).all()
            }
            if "vector_v2" not in existing_columns:
                conn.execute(text("ALTER TABLE embeddings ADD COLUMN vector_v2 vector"))

            rows = conn.execute(text('SELECT chunk_id, "vector" FROM embeddings')).all()
            for chunk_id, vector in rows:
                if vector is None:
                    continue
                vector_text = "[" + ",".join(str(float(value)) for value in vector) + "]"
                conn.execute(
                    text(
                        'UPDATE embeddings SET vector_v2 = CAST(:vector_value AS vector) WHERE chunk_id = :chunk_id'
                    ),
                    {"vector_value": vector_text, "chunk_id": chunk_id},
                )

            conn.execute(text('ALTER TABLE embeddings DROP COLUMN "vector"'))
            conn.execute(text("ALTER TABLE embeddings RENAME COLUMN vector_v2 TO vector"))

    @staticmethod
    def _ensure_pgvector_indexes(engine) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS embeddings_vector_hnsw_idx
                    ON embeddings
                    USING hnsw (vector vector_cosine_ops)
                    """
                )
            )

    @staticmethod
    def _discover_embedding_dimension(engine) -> int | None:
        with engine.begin() as conn:
            row = conn.execute(text("SELECT dimension FROM embeddings LIMIT 1")).scalar_one_or_none()
            return int(row) if row is not None else None

    @staticmethod
    def _normalize_pgvector_dimension(engine, dimension: int) -> None:
        with engine.begin() as conn:
            current_type = conn.execute(
                text(
                    """
                    SELECT format_type(a.atttypid, a.atttypmod)
                    FROM pg_attribute a
                    JOIN pg_class c ON a.attrelid = c.oid
                    WHERE c.relname = 'embeddings'
                      AND a.attname = 'vector'
                      AND NOT a.attisdropped
                    """
                )
            ).scalar_one_or_none()
            expected_type = f"vector({dimension})"
            if current_type == expected_type:
                return
            conn.execute(text("DROP INDEX IF EXISTS embeddings_vector_hnsw_idx"))
            conn.execute(
                text(
                    f"ALTER TABLE embeddings ALTER COLUMN vector TYPE vector({dimension}) USING vector::vector({dimension})"
                )
            )
