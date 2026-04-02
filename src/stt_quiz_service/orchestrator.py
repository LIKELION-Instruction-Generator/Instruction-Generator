from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Callable
import os
import time
from uuid import uuid4

from stt_quiz_service.agents.mock_backend import MockGenerationBackend
from stt_quiz_service.agents.pydantic_ai_backend import PydanticAIBackend
from stt_quiz_service.agents.weekly_backend import (
    MockWeeklyGenerationBackend,
    PydanticAIWeeklyGenerationBackend,
)
from stt_quiz_service.config import Settings
from stt_quiz_service.schemas import (
    BundleResponse,
    CorpusDocument,
    DailyTermCandidates,
    GenerateBundleRequest,
    GenerateGuideRequest,
    GenerateQuizRequest,
    IndexResponse,
    IngestResponse,
    LectureTargetDocument,
    PipelineBuildWeeklyTopicsRequest,
    PipelineBuildWeeklyTopicsResponse,
    PipelineExtractTermCandidatesRequest,
    PipelineExtractTermCandidatesResponse,
    PipelineGenerateRequest,
    PipelineGenerateWeeklyGuidesRequest,
    PipelineGenerateWeeklyGuidesResponse,
    PipelineGenerateWeeklyQuizzesRequest,
    PipelineGenerateWeeklyQuizzesResponse,
    PipelineIndexRequest,
    PipelinePrepareRequest,
    PrepareResponse,
    QuizSet,
    RunLog,
    StudyGuide,
    ConceptTerm,
    WeeklyBundleResponse,
    WeeklyConceptMapResponse,
    WeeklyGuide,
    WeeklyQuizLearnerSet,
    WeeklyQuizSet,
    WeeklyQuizSubmissionDetailResponse,
    WeeklyQuizSubmissionRequest,
    WeeklyQuizSubmissionResponse,
    WeeklyReport,
    WeeklyReportResponse,
    WeeklyTopicSet,
)
from stt_quiz_service.services.embeddings import build_embedder
from stt_quiz_service.services.ingestion import ingest_transcripts, load_curriculum_rows
from stt_quiz_service.services.quiz_profiles import build_profile_plan, summarize_profile_distribution
from stt_quiz_service.services.weekly_learner_memo import (
    MockWeeklyLearnerMemoGenerator,
    PydanticAIWeeklyLearnerMemoGenerator,
    generate_weekly_learner_memo,
)
from stt_quiz_service.services.weekly_quiz_submission import grade_weekly_quiz_submission
from stt_quiz_service.services.retrieval import Retriever
from stt_quiz_service.services.stt_preprocessor import (
    MockSTTPreprocessor,
    PydanticAISTTPreprocessor,
    STTPreprocessor,
)
from stt_quiz_service.services.topic_extraction import (
    DailyTermCandidateExtractor,
    aggregate_weekly_candidates,
)
from stt_quiz_service.prompts import read_prompt_section
from stt_quiz_service.storage.repository import Repository


@dataclass(slots=True)
class WorkflowOrchestrator:
    settings: Settings
    repository: Repository
    retriever: Retriever
    backend: object
    weekly_backend: object
    weekly_learner_memo_generator: object
    weekly_quiz_generator: object | None
    preprocessor: STTPreprocessor
    candidate_extractor: DailyTermCandidateExtractor
    embedder_provider: str

    def bootstrap(self) -> None:
        self.repository.create_schema()
        self.repository.backfill_lecture_weeks(load_curriculum_rows(self.settings.curriculum_path))
        self.repository.log_audit_event(
            event_type="bootstrap",
            status="success",
            details={"database_url": self.settings.database_url},
        )

    @classmethod
    def build(cls, settings: Settings, repository: Repository) -> "WorkflowOrchestrator":
        embedder = build_embedder(settings)
        retriever = Retriever(repository, embedder)
        backend = cls._build_backend(settings)
        weekly_backend = cls._build_weekly_backend(settings)
        weekly_learner_memo_generator = cls._build_weekly_learner_memo_generator(settings)
        weekly_quiz_generator = cls._build_weekly_quiz_generator(settings, repository)
        preprocessor = cls._build_preprocessor(settings)
        return cls(
            settings=settings,
            repository=repository,
            retriever=retriever,
            backend=backend,
            weekly_backend=weekly_backend,
            weekly_learner_memo_generator=weekly_learner_memo_generator,
            weekly_quiz_generator=weekly_quiz_generator,
            preprocessor=preprocessor,
            candidate_extractor=DailyTermCandidateExtractor(settings),
            embedder_provider=embedder.provider_name,
        )

    @staticmethod
    def _has_llm_credentials() -> bool:
        return any(
            [
                os.getenv("OPENAI_API_KEY"),
                os.getenv("ANTHROPIC_API_KEY"),
                os.getenv("GOOGLE_API_KEY"),
                os.getenv("GEMINI_API_KEY"),
            ]
        )

    @classmethod
    def _build_backend(cls, settings: Settings):
        has_llm_credentials = cls._has_llm_credentials()
        if settings.llm_backend.lower() == "pydanticai" and has_llm_credentials:
            return PydanticAIBackend(settings)
        return MockGenerationBackend()

    @classmethod
    def _build_weekly_backend(cls, settings: Settings):
        has_llm_credentials = cls._has_llm_credentials()
        if settings.llm_backend.lower() == "pydanticai" and has_llm_credentials:
            return PydanticAIWeeklyGenerationBackend(settings)
        return MockWeeklyGenerationBackend()

    @classmethod
    def _build_weekly_learner_memo_generator(cls, settings: Settings):
        has_llm_credentials = cls._has_llm_credentials()
        if settings.llm_backend.lower() == "pydanticai" and has_llm_credentials:
            return PydanticAIWeeklyLearnerMemoGenerator(settings)
        return MockWeeklyLearnerMemoGenerator()

    @classmethod
    def _build_weekly_quiz_generator(
        cls,
        settings: Settings,
        repository: Repository,
    ) -> object | None:
        if os.getenv("STT_QUIZ_USE_LANGCHAIN_WEEKLY", "true").lower() == "false":
            return None
        if not settings.database_url.startswith("postgresql"):
            return None
        if not (os.getenv("OPENAI_API_KEY") and (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))):
            return None
        try:
            from stt_quiz_service.services.weekly_quiz_langchain import LangChainWeeklyQuizGenerator
        except ModuleNotFoundError:
            return None
        return LangChainWeeklyQuizGenerator.build(settings, repository)

    @classmethod
    def _build_preprocessor(
        cls,
        settings: Settings,
        preprocess_model_override: str | None = None,
    ) -> STTPreprocessor:
        if settings.llm_backend.lower() == "pydanticai" and cls._has_llm_credentials():
            return PydanticAISTTPreprocessor(
                settings,
                model_name=preprocess_model_override,
            )
        return MockSTTPreprocessor()

    def ingest(self, transcripts_root: Path, curriculum_path: Path) -> IngestResponse:
        prepare = self.prepare_corpus(
            PipelinePrepareRequest(
                transcripts_root=str(transcripts_root),
                curriculum_path=str(curriculum_path),
            )
        )
        index = self.build_index(PipelineIndexRequest(corpus_ids=prepare.corpus_ids))
        return IngestResponse(
            lectures_ingested=prepare.targets_prepared,
            chunks_ingested=index.chunks_indexed,
            target_ids=prepare.target_ids,
        )

    def prepare_corpus(self, request: PipelinePrepareRequest) -> PrepareResponse:
        manifest_path = Path(request.output_dir) / "_prepare_manifest.json"
        preprocessor = self._build_preprocessor(
            self.settings,
            preprocess_model_override=request.preprocess_model_override,
        )
        prepare_fingerprint = self._prepare_fingerprint(request, preprocessor_model=preprocessor.model_name)
        existing_manifest = self._read_manifest(manifest_path)
        manifest_response = (existing_manifest or {}).get("response", {})
        if (
            (existing_manifest or {}).get("fingerprint") == prepare_fingerprint
            and manifest_response
            and all(
                (Path(request.output_dir) / f"{corpus_id}.txt").exists()
                for corpus_id in manifest_response.get("corpus_ids", [])
            )
        ):
            response = PrepareResponse(
                corpus_version=manifest_response.get("corpus_version", f"corpus-{prepare_fingerprint[:12]}"),
                corpora_prepared=manifest_response.get("corpora_prepared", 0),
                targets_prepared=manifest_response.get("targets_prepared", 0),
                chunks_prepared=manifest_response.get("chunks_prepared", 0),
                corpus_ids=manifest_response.get("corpus_ids", []),
                target_ids=manifest_response.get("target_ids", []),
                output_dir=request.output_dir,
                skipped=True,
            )
            self._write_manifest(
                manifest_path,
                {"fingerprint": prepare_fingerprint, "response": response.model_dump(exclude={"skipped"})},
            )
            self.repository.log_audit_event(
                event_type="prepare",
                status="skipped",
                details={
                    "corpus_version": response.corpus_version,
                    "corpus_ids": response.corpus_ids,
                    "preprocessor_model": preprocessor.model_name,
                    "output_dir": request.output_dir,
                    "persist_to_db": request.persist_to_db,
                },
            )
            return response
        self.repository.log_audit_event(
            event_type="prepare",
            status="started",
            details={
                "transcripts_root": request.transcripts_root,
                "curriculum_path": request.curriculum_path,
                "preprocessor_model": preprocessor.model_name,
                "output_dir": request.output_dir,
                "persist_to_db": request.persist_to_db,
            },
        )
        try:
            corpus_docs, target_docs, chunks_by_corpus = ingest_transcripts(
                Path(request.transcripts_root),
                Path(request.curriculum_path),
                preprocessor,
            )
            if request.persist_to_db:
                self.repository.upsert_prepared_corpus(corpus_docs, target_docs, chunks_by_corpus)
            self._export_prepared_corpus(
                output_dir=Path(request.output_dir),
                corpus_docs=corpus_docs,
            )
            corpus_version = f"corpus-{uuid4().hex[:12]}"
            response = PrepareResponse(
                corpus_version=corpus_version,
                corpora_prepared=len(corpus_docs),
                targets_prepared=len(target_docs),
                chunks_prepared=sum(len(chunks) for chunks in chunks_by_corpus.values()),
                corpus_ids=[corpus.corpus_id for corpus in corpus_docs],
                target_ids=[target.lecture_id for target in target_docs],
                output_dir=request.output_dir,
                skipped=False,
            )
            self._write_manifest(
                manifest_path,
                {"fingerprint": prepare_fingerprint, "response": response.model_dump()},
            )
            self.repository.log_audit_event(
                event_type="prepare",
                status="success",
                details={
                    "corpus_version": response.corpus_version,
                    "corpora_prepared": response.corpora_prepared,
                    "targets_prepared": response.targets_prepared,
                    "chunks_prepared": response.chunks_prepared,
                    "preprocessor_model": preprocessor.model_name,
                    "output_dir": request.output_dir,
                    "persist_to_db": request.persist_to_db,
                },
            )
            return response
        except Exception as exc:
            self.repository.log_audit_event(
                event_type="prepare",
                status="failed",
                details={"error": str(exc)[:500]},
            )
            raise

    def build_index(self, request: PipelineIndexRequest) -> IndexResponse:
        corpus_ids = request.corpus_ids or self.repository.list_corpus_ids()
        index_fingerprint = self._index_fingerprint(corpus_ids)
        existing_manifest = self._read_manifest(self._index_manifest_path())
        if self.repository.has_embeddings_for_corpora(corpus_ids, provider=self.embedder_provider):
            response = IndexResponse(
                corpus_version=(existing_manifest or {}).get("response", {}).get("corpus_version", "latest"),
                corpora_indexed=len(corpus_ids),
                chunks_indexed=self.repository.count_chunks(corpus_ids),
                embedder_provider=self.embedder_provider,
                dimension=self.repository.get_embedding_dimension(self.embedder_provider)
                or self.settings.embedding_dim,
                skipped=True,
            )
            self._write_manifest(
                self._index_manifest_path(),
                {"fingerprint": index_fingerprint, "response": response.model_dump(exclude={"skipped"})},
            )
            self.repository.log_audit_event(
                event_type="index",
                status="skipped",
                details={"corpus_ids": corpus_ids, "embedder_provider": self.embedder_provider},
            )
            return response
        self.repository.log_audit_event(
            event_type="index",
            status="started",
            details={"corpus_ids": corpus_ids, "embedder_provider": self.embedder_provider},
        )
        try:
            all_chunks = self.repository.get_all_chunks(corpus_ids)
            embedder = self.retriever.embedder
            vectors = embedder.embed_documents([chunk.text for chunk in all_chunks]) if all_chunks else []
            embeddings = {
                chunk.chunk_id: vector for chunk, vector in zip(all_chunks, vectors, strict=True)
            }
            if embeddings:
                self.repository.upsert_embeddings(
                    embeddings,
                    provider=self.embedder_provider,
                    dimension=len(vectors[0]),
                )
                self.repository.ensure_vector_search_ready(len(vectors[0]))
            response = IndexResponse(
                corpus_version="latest",
                corpora_indexed=len(set(chunk.corpus_id for chunk in all_chunks)),
                chunks_indexed=len(all_chunks),
                embedder_provider=self.embedder_provider,
                dimension=len(vectors[0]) if vectors else self.settings.embedding_dim,
                skipped=False,
            )
            self._write_manifest(
                self._index_manifest_path(),
                {"fingerprint": index_fingerprint, "response": response.model_dump()},
            )
            self.repository.log_audit_event(
                event_type="index",
                status="success",
                details=response.model_dump(),
            )
            return response
        except Exception as exc:
            self.repository.log_audit_event(
                event_type="index",
                status="failed",
                details={"corpus_ids": corpus_ids, "error": str(exc)[:500]},
            )
            raise

    def generate_artifacts(self, request: PipelineGenerateRequest) -> list[RunLog]:
        corpus_ids = request.corpus_ids or [corpus.corpus_id for corpus in self.repository.list_corpora()]
        generate_fingerprint = self._generate_fingerprint(
            corpus_ids=corpus_ids,
            mode=request.mode,
            num_questions=request.num_questions,
            choice_count=request.choice_count,
        )
        existing_manifest = self._read_manifest(self._generate_manifest_path())
        if all(self.repository.latest_bundle_exists(corpus_id) for corpus_id in corpus_ids):
            self._write_manifest(
                self._generate_manifest_path(),
                {
                    "fingerprint": generate_fingerprint,
                    "corpus_ids": corpus_ids,
                    "mode": request.mode,
                    "num_questions": request.num_questions,
                },
            )
            run_logs = [self.repository.get_latest_bundle(corpus_id).run for corpus_id in corpus_ids]
            self.repository.log_audit_event(
                event_type="pipeline_generate",
                status="skipped",
                details={
                    "corpus_ids": corpus_ids,
                    "mode": request.mode,
                    "num_questions": request.num_questions,
                },
            )
            return run_logs
        run_logs: list[RunLog] = []
        self.repository.log_audit_event(
            event_type="pipeline_generate",
            status="started",
            details={
                "corpus_ids": corpus_ids,
                "mode": request.mode,
                "num_questions": request.num_questions,
                "choice_count": request.choice_count,
            },
        )
        try:
            for corpus_id in corpus_ids:
                _, _, run_log = self._generate_artifacts(
                    corpus_id=corpus_id,
                    mode=request.mode,
                    num_questions=request.num_questions,
                    choice_count=request.choice_count,
                )
                run_logs.append(run_log)
            self.repository.log_audit_event(
                event_type="pipeline_generate",
                status="success",
                details={
                    "corpus_ids": corpus_ids,
                    "mode": request.mode,
                    "generated_runs": len(run_logs),
                },
            )
            self._write_manifest(
                self._generate_manifest_path(),
                {
                    "fingerprint": generate_fingerprint,
                    "corpus_ids": corpus_ids,
                    "mode": request.mode,
                    "num_questions": request.num_questions,
                },
            )
            return run_logs
        except Exception as exc:
            self.repository.log_audit_event(
                event_type="pipeline_generate",
                status="failed",
                details={"corpus_ids": corpus_ids, "error": str(exc)[:500]},
            )
            raise

    def generate_quiz(self, request: GenerateQuizRequest) -> QuizSet:
        quiz_set, _, _ = self._generate_artifacts(
            corpus_id=request.corpus_id,
            mode=request.mode,
            num_questions=request.num_questions,
            choice_count=request.choice_count,
            include_guide=False,
        )
        return quiz_set

    def generate_guide(self, request: GenerateGuideRequest) -> StudyGuide:
        _, guide, _ = self._generate_artifacts(
            corpus_id=request.corpus_id,
            mode=request.mode,
            include_quiz=False,
        )
        return guide

    def generate_bundle(self, request: GenerateBundleRequest) -> BundleResponse:
        quiz_set, guide, run_log = self._generate_artifacts(
            corpus_id=request.corpus_id,
            mode=request.mode,
            num_questions=request.num_questions,
            choice_count=request.choice_count,
        )
        return BundleResponse(run=run_log, quiz_set=quiz_set, study_guide=guide)

    def list_lectures(self):
        return self.repository.list_corpora()

    def list_weeks(self, *, ready_only: bool = False):
        return self.repository.list_weeks(ready_only=ready_only)

    def get_run(self, run_id: str) -> RunLog:
        return self.repository.get_run(run_id)

    def get_latest_bundle(self, corpus_id: str) -> BundleResponse:
        return self.repository.get_latest_bundle(corpus_id)

    def extract_term_candidates(
        self, request: PipelineExtractTermCandidatesRequest
    ) -> PipelineExtractTermCandidatesResponse:
        corpus_ids = request.corpus_ids or self.repository.list_corpus_ids()
        extracted_count = 0
        for corpus_id in corpus_ids:
            corpus = self.repository.get_corpus(corpus_id)
            week = next((week for week in self.repository.list_weeks() if corpus_id in week.corpus_ids), None)
            if week is None:
                continue
            chunks = self.repository.get_chunks_for_corpus(corpus_id)
            cleaned_text = " ".join(chunk.text for chunk in chunks)
            payload = self.candidate_extractor.extract(
                corpus_id=corpus_id,
                week_id=week.week_id,
                cleaned_text=cleaned_text,
                chunks=chunks,
            )
            self.repository.save_daily_term_candidates(payload)
            extracted_count += 1
        self.repository.log_audit_event(
            event_type="extract_term_candidates",
            status="success",
            details={"corpus_ids": corpus_ids, "extracted_count": extracted_count},
        )
        return PipelineExtractTermCandidatesResponse(corpus_ids=corpus_ids, extracted_count=extracted_count)

    def build_weekly_topics(
        self, request: PipelineBuildWeeklyTopicsRequest
    ) -> PipelineBuildWeeklyTopicsResponse:
        week_ids = request.week_ids or [week.week_id for week in self.repository.list_weeks()]
        built_count = 0
        for week_id in week_ids:
            topic_set = self._build_weekly_topic_set(week_id)
            self.repository.save_weekly_topic_set(topic_set)
            built_count += 1
        self.repository.log_audit_event(
            event_type="build_weekly_topics",
            status="success",
            details={"week_ids": week_ids, "built_count": built_count},
        )
        return PipelineBuildWeeklyTopicsResponse(week_ids=week_ids, built_count=built_count)

    def generate_weekly_guides(
        self, request: PipelineGenerateWeeklyGuidesRequest
    ) -> PipelineGenerateWeeklyGuidesResponse:
        week_ids = request.week_ids or [week.week_id for week in self.repository.list_weeks()]
        generated_count = 0
        for week_id in week_ids:
            guide = self._generate_weekly_guide(week_id)
            self.repository.save_weekly_guide(guide)
            generated_count += 1
        self.repository.log_audit_event(
            event_type="generate_weekly_guides",
            status="success",
            details={"week_ids": week_ids, "generated_count": generated_count},
        )
        return PipelineGenerateWeeklyGuidesResponse(week_ids=week_ids, generated_count=generated_count)

    def generate_weekly_quizzes(
        self, request: PipelineGenerateWeeklyQuizzesRequest
    ) -> PipelineGenerateWeeklyQuizzesResponse:
        week_ids = request.week_ids or [week.week_id for week in self.repository.list_weeks()]
        generated_count = 0
        for week_id in week_ids:
            quiz_set = self._generate_weekly_quiz_set(week_id, num_questions=request.num_questions)
            self.repository.save_weekly_quiz_set(quiz_set)
            generated_count += 1
        self.repository.log_audit_event(
            event_type="generate_weekly_quizzes",
            status="success",
            details={
                "week_ids": week_ids,
                "generated_count": generated_count,
                "num_questions": request.num_questions,
            },
        )
        return PipelineGenerateWeeklyQuizzesResponse(week_ids=week_ids, generated_count=generated_count)

    def get_weekly_topics(self, week_id: str) -> WeeklyTopicSet:
        return self.repository.get_weekly_topic_set(week_id)

    def get_weekly_guide(self, week_id: str) -> WeeklyGuide:
        return self.repository.get_weekly_guide(week_id)

    def get_weekly_quiz(self, week_id: str) -> WeeklyQuizSet:
        return self.repository.get_weekly_quiz_set(week_id)

    def get_weekly_quiz_for_learner(self, week_id: str) -> WeeklyQuizLearnerSet:
        return self.repository.get_weekly_quiz_set(week_id).to_learner_set()

    def get_weekly_report(self, week_id: str) -> WeeklyReport:
        return self.repository.get_weekly_report(week_id)

    def get_weekly_report_response(self, week_id: str) -> WeeklyReportResponse:
        report = self.repository.get_weekly_report(week_id)
        week = self.repository.get_week(week_id)
        topic_set = self.repository.get_weekly_topic_set(week_id)
        guide = self.repository.get_weekly_guide(week_id)
        quiz_set = self.repository.get_weekly_quiz_set(week_id)
        try:
            latest_submission = self.repository.get_latest_weekly_quiz_submission(week_id)
        except KeyError:
            latest_submission = None
        learner_memo = generate_weekly_learner_memo(
            week=week,
            topic_set=topic_set,
            guide=guide,
            quiz_set=quiz_set,
            latest_submission=latest_submission,
            generator=self.weekly_learner_memo_generator,
        )
        return WeeklyReportResponse(
            **report.model_dump(),
            learner_memo=learner_memo,
        )

    def get_weekly_bundle(self, week_id: str) -> WeeklyBundleResponse:
        return WeeklyBundleResponse(
            topics=self.get_weekly_topics(week_id),
            guide=self.get_weekly_guide(week_id),
            quiz_set=self.get_weekly_quiz_for_learner(week_id),
            report=self.get_weekly_report(week_id),
        )

    def submit_weekly_quiz(
        self,
        week_id: str,
        request: WeeklyQuizSubmissionRequest,
    ) -> WeeklyQuizSubmissionResponse:
        quiz_set = self.repository.get_weekly_quiz_set(week_id)
        submission = grade_weekly_quiz_submission(quiz_set, request)
        self.repository.save_weekly_quiz_submission(submission)
        latest_submission = self.repository.get_weekly_quiz_submission_attempt(
            week_id,
            submission.attempt_id,
        )
        week = next(
            (candidate for candidate in self.repository.list_weeks() if candidate.week_id == week_id),
            None,
        )
        if week is None:
            raise KeyError(f"No weekly selection found for week_id: {week_id}")
        learner_memo = generate_weekly_learner_memo(
            week=week,
            topic_set=self.repository.get_weekly_topic_set(week_id),
            guide=self.repository.get_weekly_guide(week_id),
            quiz_set=quiz_set,
            latest_submission=latest_submission,
            generator=self.weekly_learner_memo_generator,
        )
        self.repository.log_audit_event(
            event_type="weekly_quiz_submit",
            status="success",
            details={
                "attempt_id": submission.attempt_id,
                "week_id": week_id,
                "total_questions": submission.total_questions,
                "answered_count": len(request.answers),
                "correct_count": submission.correct_count,
                "score": submission.score,
            },
        )
        return submission.model_copy(update={"learner_memo": learner_memo})

    def get_latest_weekly_quiz_submission(self, week_id: str) -> WeeklyQuizSubmissionDetailResponse:
        return self.repository.get_latest_weekly_quiz_submission(week_id)

    def get_weekly_quiz_submission_attempt(
        self,
        week_id: str,
        attempt_id: str,
    ) -> WeeklyQuizSubmissionDetailResponse:
        return self.repository.get_weekly_quiz_submission_attempt(week_id, attempt_id)

    def list_audit_events(self, limit: int = 100):
        return self.repository.list_audit_events(limit=limit)

    def import_daily_term_candidate_seed(
        self,
        seed_path: Path,
        *,
        week_id: str | None = None,
        corpus_ids: list[str] | None = None,
    ) -> list[str]:
        imported_corpus_ids: list[str] = []
        requested_corpus_ids = set(corpus_ids or [])
        with seed_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                row = json.loads(line)
                payload = row.get("payload", row)
                candidate_set = DailyTermCandidates.model_validate(payload)
                if week_id and candidate_set.week_id != week_id:
                    continue
                if requested_corpus_ids and candidate_set.corpus_id not in requested_corpus_ids:
                    continue
                self.repository.save_daily_term_candidates(candidate_set)
                imported_corpus_ids.append(candidate_set.corpus_id)
        self.repository.log_audit_event(
            event_type="import_daily_term_candidate_seed",
            status="success",
            details={
                "seed_path": str(seed_path),
                "week_id": week_id or "",
                "corpus_ids": imported_corpus_ids,
                "imported_count": len(imported_corpus_ids),
            },
        )
        return imported_corpus_ids

    def import_weekly_topic_set_seed(self, seed_path: Path) -> WeeklyTopicSet:
        payload = WeeklyTopicSet.model_validate_json(seed_path.read_text(encoding="utf-8"))
        self.repository.save_weekly_topic_set(payload)
        self.repository.log_audit_event(
            event_type="import_weekly_topic_set_seed",
            status="success",
            details={
                "seed_path": str(seed_path),
                "week_id": payload.week_id,
                "topic_axis_count": len(payload.topic_axes),
            },
        )
        return payload

    def generate_seeded_weekly_bundle(
        self,
        *,
        week_id: str,
        candidate_seed_path: Path,
        topic_seed_path: Path,
        num_questions: int,
    ) -> WeeklyBundleResponse:
        week = self.repository.get_week(week_id)
        imported_corpus_ids = self.import_daily_term_candidate_seed(
            candidate_seed_path,
            week_id=week_id,
            corpus_ids=week.corpus_ids,
        )
        topic_set = self.import_weekly_topic_set_seed(topic_seed_path)
        if topic_set.week_id != week_id:
            raise ValueError(
                f"weekly topic seed week_id mismatch: expected={week_id} actual={topic_set.week_id}"
            )
        guide = self._generate_weekly_guide(week_id)
        self.repository.save_weekly_guide(guide)
        quiz_set = self._generate_weekly_quiz_set(week_id, num_questions=num_questions)
        self.repository.save_weekly_quiz_set(quiz_set)
        report = self.repository.get_weekly_report(week_id)
        self.repository.log_audit_event(
            event_type="generate_seeded_weekly_bundle",
            status="success",
            details={
                "week_id": week_id,
                "candidate_seed_path": str(candidate_seed_path),
                "topic_seed_path": str(topic_seed_path),
                "seed_candidates_loaded": bool(imported_corpus_ids),
                "seed_topic_set_loaded": True,
                "candidate_extraction_skipped": True,
                "imported_corpus_ids": imported_corpus_ids,
                "num_questions": num_questions,
                "quiz_item_count": len(quiz_set.items),
            },
        )
        return WeeklyBundleResponse(
            topics=topic_set,
            guide=guide,
            quiz_set=quiz_set.to_learner_set(),
            report=report,
        )

    def get_weekly_concepts(self, week_id: str) -> WeeklyConceptMapResponse:
        candidate_sets = self.repository.list_daily_term_candidates_for_week(week_id)
        if not candidate_sets:
            raise KeyError(f"No term candidates for week_id: {week_id}")
        aggregated = aggregate_weekly_candidates(candidate_sets, limit=60)
        if not aggregated:
            raise KeyError(f"No aggregated terms for week_id: {week_id}")
        scores = [t.score for t in aggregated]
        terms = [
            ConceptTerm(term=t.term, score=t.score, rank=idx + 1)
            for idx, t in enumerate(aggregated)
        ]
        return WeeklyConceptMapResponse(
            week_id=week_id,
            terms=terms,
            max_score=max(scores),
            min_score=min(scores),
        )

    def _build_weekly_topic_set(self, week_id: str) -> WeeklyTopicSet:
        week = self.repository.get_week(week_id)
        candidate_sets = self.repository.list_daily_term_candidates_for_week(week_id)
        missing_corpus_ids = [corpus_id for corpus_id in week.corpus_ids if corpus_id not in {item.corpus_id for item in candidate_sets}]
        if missing_corpus_ids:
            self.extract_term_candidates(PipelineExtractTermCandidatesRequest(corpus_ids=missing_corpus_ids))
            candidate_sets = self.repository.list_daily_term_candidates_for_week(week_id)
        aggregated = aggregate_weekly_candidates(candidate_sets)
        aggregated_set = DailyTermCandidates(
            corpus_id=f"week-{week_id}",
            week_id=week_id,
            candidates=aggregated,
        )
        chunks = self.repository.get_week_chunks(week_id)
        return self.weekly_backend.build_weekly_topic_set(week, [aggregated_set], chunks)

    def _generate_weekly_guide(self, week_id: str) -> WeeklyGuide:
        week = self.repository.get_week(week_id)
        try:
            topic_set = self.repository.get_weekly_topic_set(week_id)
        except KeyError:
            topic_set = self._build_weekly_topic_set(week_id)
            self.repository.save_weekly_topic_set(topic_set)
        chunks = self.repository.get_week_chunks(week_id)
        return self.weekly_backend.generate_weekly_guide(week, topic_set, chunks)

    def _generate_weekly_quiz_set(
        self,
        week_id: str,
        *,
        num_questions: int,
        progress_callback: Callable[[str], None] | None = None,
    ) -> WeeklyQuizSet:
        week = self.repository.get_week(week_id)
        try:
            topic_set = self.repository.get_weekly_topic_set(week_id)
        except KeyError:
            topic_set = self._build_weekly_topic_set(week_id)
            self.repository.save_weekly_topic_set(topic_set)
        if self.weekly_quiz_generator is not None:
            return self.weekly_quiz_generator.generate_weekly_quiz_set(
                week,
                topic_set,
                num_questions=num_questions,
                progress_callback=progress_callback,
            )
        chunks = self.repository.get_week_chunks(week_id)
        return self.weekly_backend.generate_weekly_quiz_set(week, topic_set, chunks, num_questions=num_questions)

    @staticmethod
    def _pipeline_state_dir() -> Path:
        path = Path("artifacts/pipeline_state")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def _index_manifest_path(cls) -> Path:
        return cls._pipeline_state_dir() / "index_manifest.json"

    @classmethod
    def _generate_manifest_path(cls) -> Path:
        return cls._pipeline_state_dir() / "generate_manifest.json"

    @staticmethod
    def _read_manifest(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _write_manifest(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _file_signature(path: Path) -> dict[str, int | str]:
        stat = path.stat()
        return {
            "path": str(path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }

    def _prepare_fingerprint(self, request: PipelinePrepareRequest, *, preprocessor_model: str) -> str:
        transcripts_root = Path(request.transcripts_root)
        transcript_files = sorted(transcripts_root.glob("*.txt"))
        payload = {
            "transcripts": [self._file_signature(path) for path in transcript_files],
            "curriculum": self._file_signature(Path(request.curriculum_path)),
            "preprocess_model": preprocessor_model,
            "preprocess_block_chars": self.settings.preprocess_block_chars,
            "persist_to_db": request.persist_to_db,
            "prompt_hash": self._fingerprint(read_prompt_section("STT Preprocessing System Prompt")),
        }
        return self._fingerprint(payload)

    def _index_fingerprint(self, corpus_ids: list[str]) -> str:
        payload = {
            "corpus_ids": sorted(corpus_ids),
            "embedder_provider": self.embedder_provider,
            "embedding_backend": self.settings.embedding_backend,
            "embedding_dim": self.settings.embedding_dim,
            "openai_embedding_model": self.settings.openai_embedding_model,
        }
        return self._fingerprint(payload)

    def _generate_fingerprint(
        self,
        *,
        corpus_ids: list[str],
        mode: str,
        num_questions: int,
        choice_count: int | None,
    ) -> str:
        payload = {
            "corpus_ids": sorted(corpus_ids),
            "mode": mode,
            "num_questions": num_questions,
            "choice_count": choice_count,
            "default_model": self.settings.default_model,
            "top_k": self.settings.top_k,
            "prompt_hash": self._fingerprint(
                {
                    "shared": read_prompt_section("Shared Rules"),
                    "quiz": read_prompt_section("Quiz Generation System Prompt"),
                    "guide": read_prompt_section("Study Guide System Prompt"),
                    "eval": read_prompt_section("Evaluation System Prompt"),
                }
            ),
        }
        return self._fingerprint(payload)

    @staticmethod
    def _export_prepared_corpus(*, output_dir: Path, corpus_docs: list[CorpusDocument]) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        expected_names = {"_prepare_manifest.json"}
        for corpus_doc in corpus_docs:
            expected_names.add(f"{corpus_doc.corpus_id}.txt")
            expected_names.add(f"{corpus_doc.corpus_id}.json")
        for path in output_dir.iterdir():
            if path.is_file() and path.name not in expected_names and path.suffix in {".txt", ".json"}:
                path.unlink()
        for corpus_doc in corpus_docs:
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

    def _generate_artifacts(
        self,
        *,
        corpus_id: str,
        mode: str,
        num_questions: int = 5,
        choice_count: int | None = None,
        include_quiz: bool = True,
        include_guide: bool = True,
    ):
        run_log = None
        context_chunks = []
        retrieval_hits = []
        retrieval_query = ""
        retrieval_top_k = 0
        quiz_set = None
        profile_plan = None
        started = time.perf_counter()
        try:
            corpus = self.repository.get_corpus(corpus_id)
            chunks = self.repository.get_chunks_for_corpus(corpus_id)
            context_chunks = chunks
            if mode == "rag":
                retrieval_top_k = self.settings.top_k
                retrieval_result = self.retriever.retrieve_with_scores(
                    corpus,
                    top_k=self.settings.top_k,
                    exclude_practice=self.settings.exclude_practice_examples,
                )
                retrieval_query = retrieval_result.query
                retrieval_hits = retrieval_result.hits
                context_chunks = [hit.to_chunk_document() for hit in retrieval_hits]
            if not context_chunks:
                context_chunks = chunks[: self.settings.top_k]
                if not retrieval_query:
                    retrieval_query = "fallback_to_first_chunks"
            if include_quiz:
                profile_plan = build_profile_plan(
                    corpus,
                    context_chunks,
                    num_questions=num_questions,
                    preferred_choice_count=choice_count,
                )
            self.repository.log_audit_event(
                event_type="generation",
                status="started",
                lecture_id=corpus_id,
                details={
                    "mode": mode,
                    "num_questions": num_questions,
                    "choice_count_preference": choice_count,
                    "include_quiz": include_quiz,
                    "include_guide": include_guide,
                    "backend": getattr(self.backend, "model_name", "unknown"),
                    "retrieval_query": retrieval_query,
                    "retrieval_top_k": retrieval_top_k,
                    "eligible_profiles": profile_plan["eligible_profiles"] if profile_plan else [],
                    "target_profile_distribution": profile_plan["profile_counts"] if profile_plan else {},
                },
            )
            quiz_set = (
                self.backend.generate_quiz_set(
                    corpus,
                    context_chunks,
                    mode=mode,
                    num_questions=num_questions,
                    choice_count=choice_count,
                )
                if include_quiz
                else QuizSet(corpus_id=corpus_id, mode=mode, items=[], model_info={})
            )
            study_guide = (
                self.backend.generate_study_guide(corpus, context_chunks, mode=mode)
                if include_guide
                else StudyGuide(
                    corpus_id=corpus_id,
                    summary="",
                    key_concepts=[],
                    review_points=[],
                    common_confusions=[],
                    recommended_review_order=[],
                )
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            evaluation = self.backend.evaluate(
                corpus,
                context_chunks,
                quiz_set,
                study_guide,
                mode=mode,
                latency_ms=latency_ms,
                token_cost_hint=0.0,
            )
            quiz_set.evaluation_summary = evaluation.model_dump(
                include={"faithfulness_score", "clarity_score", "duplication_score", "coverage_score"}
            )
            profile_distribution = summarize_profile_distribution(quiz_set.items)
            run_log = self.repository.save_bundle(
                corpus_id=corpus_id,
                mode=mode,
                model_name=getattr(self.backend, "model_name", "unknown"),
                retrieval_query=retrieval_query,
                retrieved_chunk_ids=[chunk.chunk_id for chunk in context_chunks],
                retrieval_hits=retrieval_hits,
                retrieval_top_k=retrieval_top_k,
                embedder_provider=self.embedder_provider,
                profile_distribution=profile_distribution,
                latency_ms=latency_ms,
                token_usage=0,
                evaluation=evaluation,
                quiz_set=quiz_set,
                study_guide=study_guide,
            )
            self.repository.log_audit_event(
                event_type="generation",
                status="success",
                lecture_id=corpus_id,
                run_id=run_log.run_id,
                details={
                    "mode": mode,
                    "retrieved_chunk_count": len(context_chunks),
                    "retrieval_query": retrieval_query,
                    "quiz_items": len(quiz_set.items),
                    "profile_distribution": profile_distribution,
                    "guide_concepts": len(study_guide.key_concepts),
                    "latency_ms": latency_ms,
                    "model_name": run_log.model_name,
                },
            )
            return quiz_set, study_guide, run_log
        except Exception as exc:
            self.repository.log_audit_event(
                event_type="generation",
                status="failed",
                lecture_id=corpus_id,
                run_id=run_log.run_id if run_log else None,
                details={
                    "mode": mode,
                    "target_num_questions": num_questions,
                    "choice_count_preference": choice_count,
                    "eligible_profiles": profile_plan["eligible_profiles"] if profile_plan else [],
                    "target_profile_distribution": profile_plan["profile_counts"] if profile_plan else {},
                    "actual_generated_items": len(quiz_set.items) if quiz_set else 0,
                    "retrieved_chunk_count": len(context_chunks),
                    "retrieval_query": retrieval_query,
                    "error": str(exc)[:500],
                },
            )
            raise
