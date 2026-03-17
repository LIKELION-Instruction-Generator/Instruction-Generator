# Local Week 1 Seeded Baseline Progress

## Status
- Current status: **COMPLETE**
- This document is the active checklist/log for the current local baseline path.
- 이 문서는 baseline acceptance 기준 문서이며, 아래 checklist는 원래 read-only stabilization 단계까지를 닫은 기록이다.
- 이후 추가된 submit / latest submission / learner memo API 상태는 아래 `Current backend API state` 섹션에 현재 코드 기준으로 반영한다.
- The baseline is valid only when the full week 1 bundle is accepted:
  - `weekly_1_guide.json`
  - `weekly_1_quiz.json`
  - `weekly_1_report.json`

## Baseline Contract (active)
- week 1 baseline is **seed-reuse only**
- upstream keyword/topic extraction is **fixed** and must not rerun
- fixed seeds:
  - `artifacts/runpod_fetch/gpu_backup_20260317/daily_term_candidates_export.jsonl`
  - `artifacts/runpod_fetch/gpu_backup_20260317/weekly_1_topic_set.json`
- any rerun that logs candidate extraction / YAKE / KeyBERT / weekly topic rebuilding is a **discarded path**
- retrieval chunking for quiz is rebuilt from **preprocessed STT** using:
  - `RecursiveCharacterTextSplitter`
  - `chunk_size=800`
  - `chunk_overlap=100`
- quiz remains `LangChain` strict-RAG only
- week 1 quiz contract stays:
  - 5 corpora
  - 5 items per corpus
  - total 25 items

## Goal
- Reuse server-fetched seeds for week 1 baseline.
- Do not rerun YAKE/KeyBERT/Gemini upstream extraction.
- Generate and validate the baseline bundle outputs:
  - `weekly_1_guide.json`
  - `weekly_1_quiz.json`
  - `weekly_1_report.json`

## Inputs (fixed)
- `artifacts/runpod_fetch/gpu_backup_20260317/daily_term_candidates_export.jsonl`
- `artifacts/runpod_fetch/gpu_backup_20260317/weekly_1_topic_set.json`

## Checklist
- [x] Add orchestrator-level seed import helpers
- [x] Add orchestrator-level seeded bundle generation path
- [x] Add seeded baseline mode flag to weekly build entrypoint
- [x] Add seed import path for daily term candidates
- [x] Add seed import path for weekly topic set
- [x] Skip candidate extraction and topic rebuilding in seeded mode
- [x] Define active retrieval path as recursive re-chunking from preprocessed STT (`800/100`)
- [x] Define discarded path explicitly: prepared corpus chunk reuse for quiz retrieval
- [x] Print required seeded logs:
  - `seed_candidates_loaded=true`
  - `seed_topic_set_loaded=true`
  - `candidate_extraction_skipped=true`
- [x] Guard seeded baseline against non-LangChain fallback
- [x] Print explicit strict-RAG runtime markers:
  - `quiz_generation_path=langchain_strict_rag`
  - `retrieval_chunking=recursive chunk_size=800 chunk_overlap=100`
  - `quiz_contract_items=true actual=... expected=25`
- [x] Run seeded baseline execution and confirm bundle outputs are refreshed
- [x] Validate week 1 acceptance gates across the full bundle (guide + quiz + report)
- [x] Run targeted weekly pipeline regression tests
- [x] Confirm seeded execution logs explicitly show:
  - `seed_candidates_loaded=true`
  - `seed_topic_set_loaded=true`
  - `candidate_extraction_skipped=true`
  - recursive `800/100`
  - quiz total `25 items`
- [x] Keep status as incomplete until all three bundle artifacts pass acceptance
- [x] Sync accepted week 1 bundle into DB read model without upstream rerun
- [x] Make `/weeks` viewer-ready only so it does not advertise missing bundles
- [x] Verify live `PostgreSQL + FastAPI` responses for `/health`, `/weeks`, `/weekly-bundle/1`
- [x] Separate read-only weekly API scope from submit/performance backlog

## Work Log
- Updated `src/stt_quiz_service/orchestrator.py`
  - Added `import_daily_term_candidate_seed(...)`
  - Added `import_weekly_topic_set_seed(...)`
  - Added `generate_seeded_weekly_bundle(...)`
  - Seeded path now imports server-fetched seeds and generates `guide / quiz / report` without upstream re-extraction

- Updated `scripts/build_weekly_for_week.py`
  - Added `--seeded-baseline`
  - Added `--seed-candidates-file`
  - Added `--seed-topic-file`
  - Seeded mode behavior:
    - imports server-fetched seed candidates
    - imports seed topic set
    - skips upstream extraction and weekly topic rebuilding
    - must log seeded markers before bundle generation
    - fails fast if the loaded seed corpus set does not exactly match week 1 corpus ids
    - fails fast if LangChain strict-RAG quiz generator is not available
    - logs strict-RAG runtime markers and expected quiz contract item count

- Updated quiz retrieval direction
  - Active path: recursive re-chunking from `CorpusSelection.cleaned_text`
  - Discarded path: reusing prepared corpus chunks for quiz retrieval

- Updated `tests/test_weekly_pipeline.py`
  - Added seeded-candidate reuse contract test
  - Strengthened weekly quiz contract assertions
  - Result: `./.venv_quizsvc/bin/pytest -q tests/test_weekly_pipeline.py` -> `2 passed`

- Updated `src/stt_quiz_service/schemas.py`
  - Added `-rag-` aware corpus id parsing for strict-RAG chunk ids
  - Reused the same parser when `TopicAxis.source_corpus_ids` is auto-populated from evidence ids

- Updated `src/stt_quiz_service/agents/weekly_backend.py`
  - Weekly guide now backfills top-level `evidence_chunk_ids` from the topic axis evidence union when the model leaves it empty

- Seeded week 1 baseline rerun completed
  - command: `./.venv_quizsvc/bin/python -u scripts/build_weekly_for_week.py --week-id 1 --seeded-baseline`
  - upstream markers confirmed:
    - `seed_candidates_loaded=true`
    - `seed_topic_set_loaded=true`
    - `candidate_extraction_skipped=true`
    - `quiz_generation_path=langchain_strict_rag`
    - `retrieval_chunking=recursive chunk_size=800 chunk_overlap=100`
    - `quiz_contract_items=true actual=25 expected=25`
  - rerun result:
    - `weekly_1_guide.json` refreshed
    - `weekly_1_quiz.json` refreshed
    - `weekly_1_report.json` refreshed

- Acceptance result
  - guide:
    - top-level `evidence_chunk_ids` count = `12`
    - evidence dates cover `2026-02-02 ~ 2026-02-06`
  - quiz:
    - total items = `25`
    - per-corpus counts = `5 / 5 / 5 / 5 / 5`
    - `bad_source_date = []`
    - `bad_retrieved = []`
    - `bad_evidence = []`
    - `bad_axis = []`
    - `absence_hits = []`
    - oversized option/explanation hits = `[]`
  - report:
    - `mismatched_axis_item_count = 0`
    - `learning_goal_source_distribution = {"generated": 25}`

- Operational read-only weekly API pass
  - Updated `src/stt_quiz_service/storage/repository.py`
    - `list_weeks(ready_only=True)` now filters out weeks without a complete weekly bundle
  - Updated `src/stt_quiz_service/orchestrator.py`
    - added `list_weeks(..., ready_only=True)` support for the viewer read path
    - LangChain weekly quiz generator is now skipped automatically on non-PostgreSQL DB URLs
  - Updated `src/stt_quiz_service/api/app.py`
    - `GET /weeks` now returns only bundle-ready weeks
  - Added `src/stt_quiz_service/services/weekly_baseline_sync.py`
    - syncs accepted `week 1` topic/guide/quiz artifacts into the DB read model
    - imports week 1 lecture metadata from curriculum + `artifacts/preprocessed/*.json`
    - verifies the computed weekly report matches `artifacts/pipeline_state/weekly_1_report.json`
  - Added `scripts/sync_weekly_read_model.py`
    - explicit CLI bootstrap for the accepted week 1 read-only viewer model
  - Updated `scripts/run_api.sh`
    - now syncs the accepted week 1 baseline before starting uvicorn
    - can be disabled with `STT_QUIZ_SYNC_ACCEPTED_WEEKLY_BASELINE=false`
  - Updated `tests/test_api.py`
    - `/weeks` now tests the bundle-ready-only contract
    - accepted week 1 baseline API regression coverage added

- Operational verification result (2026-03-17)
  - startup log:
    - `database ready: postgresql+psycopg://quizsvc:quizsvc@localhost:5433/quizsvc`
    - `weekly read model synced: week_id=1 ... report_verified=true`
  - live API checks:
    - `GET /health` -> `200`, `status=ok`
    - `GET /weeks` -> `200`, count=`1`, week ids=`["1"]`
    - `GET /weekly-bundle/1` -> `200`, keys=`topics/guide/quiz_set/report`
    - `GET /weekly-bundle/2` -> `404`
  - accepted artifact comparison:
    - `/weekly-bundle/1.topics` == `artifacts/pipeline_state/weekly_1_topic_set.json`
    - `/weekly-bundle/1.guide` == `artifacts/pipeline_state/weekly_1_guide.json`
    - `/weekly-bundle/1.quiz_set` == `artifacts/pipeline_state/weekly_1_quiz.json`
    - `/weekly-bundle/1.report` == `artifacts/pipeline_state/weekly_1_report.json`

- Current backend execution method
  - main start command:
    - `./scripts/run_api.sh`
  - manual sync only:
    - `./.venv_quizsvc/bin/python scripts/sync_weekly_read_model.py --week-id 1`
  - disable startup sync only if explicitly needed:
    - `STT_QUIZ_SYNC_ACCEPTED_WEEKLY_BASELINE=false ./scripts/run_api.sh`

- Current backend API state
  - `GET /health`: DB reachability + actual `database_url`
  - `GET /weeks`: viewer-ready weeks only
  - `GET /weekly-bundle/{week_id}`: accepted bundle for `week_id=1`
  - `GET /weekly-quiz/{week_id}`: learner-facing payload only, answer key 직접 비노출
  - `POST /weekly-quiz/{week_id}/submit`: 전 문항 응답 필요, score/correct_count/results/learner_memo 반환
  - `GET /weekly-quiz/{week_id}/latest-submission`: latest review payload
  - `GET /weekly-quiz/{week_id}/attempts/{attempt_id}`: attempt-specific review payload
  - `GET /weekly-report/{week_id}`: static coverage report + dynamic learner_memo
  - remaining metadata mismatch:
    - `/weekly-bundle/{week_id}` still omits `WeeklySelection` metadata, so the frontend must keep joining `/weeks` + `/weekly-bundle/{week_id}`
    - report는 latest submission 기반 feedback까지 포함하지만, multi-attempt learner performance report는 아직 아님

- Backend backlog after the baseline runtime pass
  - multi-attempt learner performance storage/reporting
  - `/weekly-bundle/{week_id}` display metadata 정리 여부 결정

## Notes
- This document is the single checklist/log file for the current local week 1 baseline task.
- Active execution path:
  - `./.venv_quizsvc/bin/python -u scripts/build_weekly_for_week.py --week-id 1 --seeded-baseline`
  - `./scripts/run_api.sh`
- Discarded execution paths:
  - any default `build_weekly_for_week.py` run that triggers candidate extraction
  - any rerun that rebuilds `weekly_topic_set`
  - any quiz retrieval path based on prepared corpus chunks
- Explicitly out of scope for the current operational read-only pass:
  - any other week bundle acceptance
  - upstream topic extraction reruns
  - multi-attempt learner performance storage/reporting
- Baseline pass criteria are now satisfied for week 1. Further work should start from this accepted seed-reuse bundle.
