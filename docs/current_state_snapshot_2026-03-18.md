# STT Quiz Service Current State Snapshot (2026-03-18)

이 문서는 **기존 `README.md`의 상태 스냅샷 역할**을 이어받는다.

목적:
- 현재 구현 상태를 빠르게 확인
- accepted week 1 baseline / runtime / 현재 API 계약을 한 문서에서 요약
- GitHub 첫 화면용 `README.md`와 분리

## Current baseline

현재 기준 상태는 `week 1 accepted seeded baseline`입니다.

- upstream topic extraction은 seed 재사용
- weekly quiz는 `LangChain strict RAG`
- 학생용 표면은 `interactive weekly web app`

## Current stack

- `FastAPI`
- `PostgreSQL + pgvector`
- `SQLAlchemy`
- `LangChain`
- `OpenAI Embeddings`
- `Gemini`
- `YAKE + KeyBERT`
- `React + Vite + Tailwind CSS`

## Current product surface

- `weekly topic set`
- `weekly guide`
- `weekly quiz`
  - learner-facing 문제 조회
  - 제출 / 채점 / latest review
  - solve-time `source_date` 비노출
- `weekly report`
  - 정적 coverage report
  - latest submission 기반 learner memo
  - latest wrong-answer review (`오답만`, `2개씩` pagination)
- `frontend/` 기반 weekly web app
  - hub: 병합된 weekly core 섹션 + 3개 sidebar nav
  - topic-axis cards: 전체 `source_corpus_ids` 표시
  - submit 직후 hub/report에 cached learner memo + latest submission 즉시 반영

주의:
- 현재 `weekly report`는 **정적 coverage report + 최신 제출 기반 learner memo + 오답 리뷰** 조합입니다.
- 현재 `learner performance`는 latest submission 중심이며, 장기 누적 성과 분석은 아직 backlog입니다.
- `Streamlit`은 더 이상 현재 제품 기준 UI가 아닙니다.

## Current-state docs

아래 문서를 현재 상태 판단의 기준으로 봅니다.

- 현재 상태 스냅샷: `docs/current_state_snapshot_2026-03-18.md`
- 시스템 구조: `docs/architecture.md`
- accepted baseline 상태: `docs/local_week1_baseline_progress.md`
- 다음 단계 로드맵: `docs/roadmap_after_baseline_2026-03-17.md`
- 배포/데이터 번들 기준: `docs/deployment_runtime_bundle.md`
- 문서 분류/정리 기준: `docs/documentation_map.md`

## Repository layout

- `src/stt_quiz_service`: 백엔드 서비스 코드
- `frontend`: React/Vite/Tailwind 프론트엔드
- `docs`: 현재 구조/실행/작업 기록 문서
- `tests`: 단위 및 통합 테스트
- `artifacts/pipeline_state`: 최신 generated weekly artifacts
- `artifacts/runpod_fetch`: Runpod에서 가져온 historical 자료

## Current workflow

1. 데이터 전처리
2. daily supporting term 후보 추출
3. weekly topic axis 생성
4. weekly guide 생성
5. strict RAG weekly quiz 생성
6. weekly report 생성
7. API serve
8. frontend web app 연결

## Topic extraction

- daily 후보 추출: `YAKE + KeyBERT`
- weekly 통합: `Gemini`
- current baseline에서는 upstream을 다시 돌리지 않고 seed를 재사용합니다.

Seed 기준:
- `artifacts/runpod_fetch/gpu_backup_20260317/daily_term_candidates_export.jsonl`
- `artifacts/runpod_fetch/gpu_backup_20260317/weekly_1_topic_set.json`

## Quiz generation

현재 weekly quiz는 `strict RAG` 경로를 사용합니다.

- chunk source: preprocessed STT
- splitter: `RecursiveCharacterTextSplitter`
- `chunk_size=800`
- `chunk_overlap=100`
- embeddings: `OpenAIEmbeddings(text-embedding-3-small)`
- store: `PostgreSQL + pgvector`
- generation path:
  - retrieval
  - claim extraction
  - question planning
  - item generation
  - validation

계약:
- 주차 표시 단위는 weekly
- 생성 계약은 STT 1개당 최소 5문항

## Dynamic app run order

1. PostgreSQL
   - `./scripts/start_postgres.sh`
2. API
   - `./scripts/run_api.sh`
   - 기본 동작:
     - Postgres readiness 확인
     - accepted `week 1` bundle DB sync
     - FastAPI 실행
   - startup sync를 끄고 싶으면:
     - `STT_QUIZ_SYNC_ACCEPTED_WEEKLY_BASELINE=false ./scripts/run_api.sh`
   - 수동 sync만 먼저 하고 싶으면:
     - `./.venv_quizsvc/bin/python scripts/sync_weekly_read_model.py --week-id 1`
   - runtime data 선검증:
     - `./.venv_quizsvc/bin/python scripts/check_runtime_data_bundle.py --week-id 1`
3. Frontend
   - `cd frontend && npm run dev`
4. 확인
   - `curl http://127.0.0.1:8000/weeks`
   - `http://127.0.0.1:5173/weeks/1/hub`
   - `http://127.0.0.1:5173/weeks/1/quiz`
   - `http://127.0.0.1:5173/weeks/1/report`

코드/데이터 분리 배포는 `docs/deployment_runtime_bundle.md`를 따른다.

## Key APIs

- `GET /health`
- `GET /weeks`
- `GET /weekly-topics/{week_id}`
- `GET /weekly-guide/{week_id}`
- `GET /weekly-quiz/{week_id}`
- `POST /weekly-quiz/{week_id}/submit`
- `GET /weekly-quiz/{week_id}/latest-submission`
- `GET /weekly-quiz/{week_id}/attempts/{attempt_id}`
- `GET /weekly-report/{week_id}`
- `GET /weekly-bundle/{week_id}`

현재 app 기준 API 규칙:
- `GET /weeks`는 `weekly bundle`이 준비된 주차만 반환합니다.
- `GET /weekly-bundle/{week_id}`는 여전히 `WeeklySelection` 메타데이터를 포함하지 않으므로, 프론트는 `/weeks`와 join해야 합니다.
- `GET /weekly-quiz/{week_id}`는 learner-facing payload이며 `answer_index`, `answer_text`, `explanation`을 직접 노출하지 않습니다.
- `POST /weekly-quiz/{week_id}/submit`은 **전 문항 응답**이 아니면 `422`를 반환합니다.
- `POST /weekly-quiz/{week_id}/submit` 응답에는 `attempt_id`, `submitted_at`, `total_questions`, `correct_count`, `score`, `results`, `learner_memo`가 포함됩니다.
- `GET /weekly-quiz/{week_id}/latest-submission`과 `GET /weekly-quiz/{week_id}/attempts/{attempt_id}`는 제출 후 review payload를 반환합니다.
- `GET /weekly-report/{week_id}`는 정적 coverage report 필드에 dynamic `learner_memo`를 추가해 반환합니다.
- `learner_memo`와 latest submission review는 runtime dynamic layer이며, accepted artifact JSON 자체를 mutate하지 않습니다.
- 제출 후 허브/리포트는 latest submission과 learner memo를 즉시 반영합니다.

## Week 1 accepted baseline

현재 accepted baseline 결과:

- `weekly_1_guide.json`
- `weekly_1_quiz.json`
- `weekly_1_report.json`

검증 상태:
- quiz 총 `25문항`
- corpus별 `5문항`
- `topic/source` mismatch `0`
- `retrieved/evidence` mismatch `0`
- guide evidence 날짜 `2026-02-02 ~ 2026-02-06`
- report `mismatched_axis_item_count = 0`

상세는 `docs/local_week1_baseline_progress.md`를 봅니다.

## Notes

- `.env`는 자동 로드됩니다.
- 테스트/오프라인 개발에서는 SQLite fallback이 남아 있지만, 현재 기준 경로는 PostgreSQL입니다.
- accepted `week 1` runtime surface 자체는 LLM API key 없이도 올라갈 수 있습니다. `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_API_KEY`는 generation/LLM 경로나 strict RAG 재생성에 필요합니다.
- GitHub에는 코드만 올리고, private data는 별도 runtime bundle로 공유하는 것을 전제로 합니다.
- historical 문서와 prompt archive는 삭제하지 않고 보존합니다. 어떤 문서가 현재 기준인지 여부는 `docs/documentation_map.md`에 정리합니다.
