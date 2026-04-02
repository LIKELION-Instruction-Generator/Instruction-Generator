from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from stt_quiz_service.config import load_settings
from stt_quiz_service.orchestrator import WorkflowOrchestrator
from stt_quiz_service.schemas import (
    GenerateBundleRequest,
    GenerateGuideRequest,
    GenerateQuizRequest,
    IngestRequest,
    PipelineBuildWeeklyTopicsRequest,
    PipelineExtractTermCandidatesRequest,
    PipelineGenerateRequest,
    PipelineGenerateWeeklyGuidesRequest,
    PipelineGenerateWeeklyQuizzesRequest,
    PipelineIndexRequest,
    PipelinePrepareRequest,
    WeeklyQuizSubmissionRequest,
)
from stt_quiz_service.storage.db import build_engine, build_session_factory
from stt_quiz_service.storage.repository import Repository


def create_app() -> FastAPI:
    settings = load_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    repository = Repository(session_factory)
    orchestrator = WorkflowOrchestrator.build(settings, repository)
    try:
        orchestrator.bootstrap()
    except OperationalError as exc:
        raise RuntimeError(
            "Database connection failed. Start PostgreSQL first, then retry. "
            "Expected STT_QUIZ_DATABASE_URL to be reachable."
        ) from exc

    app = FastAPI(title="STT Quiz Service")
    app.state.orchestrator = orchestrator
    app.state.database_url = settings.database_url

    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "STT_QUIZ_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health")
    def health():
        try:
            app.state.orchestrator.repository.ping()
        except OperationalError as exc:
            raise HTTPException(status_code=503, detail="database unavailable") from exc
        return {"status": "ok", "database_url": app.state.database_url}

    @app.post("/ingest")
    def ingest(request: IngestRequest):
        return app.state.orchestrator.ingest(
            Path(request.transcripts_root), Path(request.curriculum_path)
        )

    @app.post("/pipeline/prepare")
    def pipeline_prepare(request: PipelinePrepareRequest):
        return app.state.orchestrator.prepare_corpus(request)

    @app.post("/pipeline/index")
    def pipeline_index(request: PipelineIndexRequest):
        return app.state.orchestrator.build_index(request)

    @app.post("/pipeline/generate")
    def pipeline_generate(request: PipelineGenerateRequest):
        try:
            return app.state.orchestrator.generate_artifacts(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/pipeline/extract-term-candidates")
    def pipeline_extract_term_candidates(request: PipelineExtractTermCandidatesRequest):
        try:
            return app.state.orchestrator.extract_term_candidates(request)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/pipeline/build-weekly-topics")
    def pipeline_build_weekly_topics(request: PipelineBuildWeeklyTopicsRequest):
        try:
            return app.state.orchestrator.build_weekly_topics(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/pipeline/generate-weekly-guides")
    def pipeline_generate_weekly_guides(request: PipelineGenerateWeeklyGuidesRequest):
        try:
            return app.state.orchestrator.generate_weekly_guides(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/pipeline/generate-weekly-quizzes")
    def pipeline_generate_weekly_quizzes(request: PipelineGenerateWeeklyQuizzesRequest):
        try:
            return app.state.orchestrator.generate_weekly_quizzes(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/lectures")
    def list_lectures():
        return app.state.orchestrator.list_lectures()

    @app.get("/weeks")
    def list_weeks():
        return app.state.orchestrator.list_weeks(ready_only=True)

    @app.get("/bundle/{corpus_id}")
    def get_latest_bundle(corpus_id: str):
        try:
            return app.state.orchestrator.get_latest_bundle(corpus_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/weekly-topics/{week_id}")
    def get_weekly_topics(week_id: str):
        try:
            return app.state.orchestrator.get_weekly_topics(week_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/weekly-guide/{week_id}")
    def get_weekly_guide(week_id: str):
        try:
            return app.state.orchestrator.get_weekly_guide(week_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/weekly-quiz/{week_id}")
    def get_weekly_quiz(week_id: str):
        try:
            return app.state.orchestrator.get_weekly_quiz_for_learner(week_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/weekly-quiz/{week_id}/submit")
    def submit_weekly_quiz(week_id: str, request: WeeklyQuizSubmissionRequest):
        try:
            return app.state.orchestrator.submit_weekly_quiz(week_id, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/weekly-quiz/{week_id}/latest-submission")
    def get_latest_weekly_quiz_submission(week_id: str):
        try:
            return app.state.orchestrator.get_latest_weekly_quiz_submission(week_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/weekly-quiz/{week_id}/attempts/{attempt_id}")
    def get_weekly_quiz_submission_attempt(week_id: str, attempt_id: str):
        try:
            return app.state.orchestrator.get_weekly_quiz_submission_attempt(week_id, attempt_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/weekly-report/{week_id}")
    def get_weekly_report(week_id: str):
        try:
            return app.state.orchestrator.get_weekly_report_response(week_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/weekly-bundle/{week_id}")
    def get_weekly_bundle(week_id: str):
        try:
            return app.state.orchestrator.get_weekly_bundle(week_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/weekly-concepts/{week_id}")
    def get_weekly_concepts(week_id: str):
        try:
            return app.state.orchestrator.get_weekly_concepts(week_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/quiz/generate")
    def generate_quiz(request: GenerateQuizRequest):
        try:
            return app.state.orchestrator.generate_quiz(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/guide/generate")
    def generate_guide(request: GenerateGuideRequest):
        try:
            return app.state.orchestrator.generate_guide(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/bundle/generate")
    def generate_bundle(request: GenerateBundleRequest):
        try:
            return app.state.orchestrator.generate_bundle(request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/runs/{run_id}")
    def get_run(run_id: str):
        try:
            return app.state.orchestrator.get_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/audit/events")
    def list_audit_events(limit: int = 100):
        return app.state.orchestrator.list_audit_events(limit=limit)

    return app
