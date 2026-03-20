# STT Quiz Service

STT 강의 스크립트와 커리큘럼을 기반으로 주차별 학습 허브, 퀴즈, 리포트를 제공하는 서비스입니다.  
현재 저장소는 **코드는 GitHub에 올리고, private 데이터는 별도 번들로 공유**하는 방식으로 운영하는 것을 전제로 합니다.

## What This Service Does

- 주차별 핵심 주제 축 생성
- 주차별 학습 가이드 생성
- strict RAG 기반 weekly quiz 제공
- quiz 제출 / 채점 / latest review 제공
- latest submission 기반 learner memo / 오답 리뷰 제공
- React web app으로 hub / quiz / report 화면 제공

## Tech Stack

- Backend: `FastAPI`, `SQLAlchemy`, `PostgreSQL + pgvector`
- LLM / Retrieval: `LangChain`, `OpenAI Embeddings`, `Gemini`, `YAKE + KeyBERT`
- Frontend: `React`, `Vite`, `Tailwind CSS`

## Repo Structure

- `src/stt_quiz_service/`: backend application code
- `frontend/`: web frontend
- `scripts/`: local run / sync / validation scripts
- `tests/`: API and pipeline tests
- `docs/`: architecture, deployment, current-state, and work docs

## Quick Start

### 1. Clone code

```bash
git clone https://github.com/LIKELION-Instruction-Generator/Instruction-Generator.git
cd Instruction-Generator
```

### 2. Copy the private runtime data bundle

아래 문서의 구조 그대로 repo root에 복사합니다.
- [deployment_runtime_bundle.md](docs/deployment_runtime_bundle.md)

### 3. Create Python environment

```bash
python3 -m venv .venv_quizsvc
./.venv_quizsvc/bin/pip install -e ".[dev]"
```

`zsh`에서는 `.[dev]`를 glob으로 해석할 수 있으므로 따옴표를 유지한다.

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Configure environment

```bash
cp .env.example .env
```

최소 권장 설정:
- `STT_QUIZ_DATABASE_URL`
- `STT_QUIZ_SYNC_ACCEPTED_WEEKLY_BASELINE=true`

generation / LLM 기능까지 쓰려면 추가:
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY` 또는 `GEMINI_API_KEY`

참고:
- accepted `week 1` runtime surface만 올릴 때는 LLM key 없이도 동작할 수 있습니다.

### 6. Validate the runtime data bundle

```bash
./.venv_quizsvc/bin/python scripts/check_runtime_data_bundle.py --week-id 1
```

정상이라면 `runtime data bundle check: ok ...`가 출력됩니다.

### 7. Start the backend

```bash
./scripts/run_api.sh
```

이 스크립트는 순서대로:
1. DB 설정 확인
2. PostgreSQL이 필요하면 `start_postgres.sh` 실행
3. accepted `week 1` read model sync
4. FastAPI 실행

### 8. Start the frontend

```bash
cd frontend
npm run dev
```

### 9. Open the app

기본 주소:
- Hub: `http://127.0.0.1:5173/weeks/1/hub`
- Quiz: `http://127.0.0.1:5173/weeks/1/quiz`
- Report: `http://127.0.0.1:5173/weeks/1/report`

Vite가 포트를 바꾸면 콘솔에 출력된 `Local:` 주소를 사용하세요.

## Backend Run Checks

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/weeks
curl http://127.0.0.1:8000/weekly-bundle/1
curl http://127.0.0.1:8000/weekly-quiz/1
curl http://127.0.0.1:8000/weekly-report/1
```

## Current API Surface

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

현재 contract 요약:
- quiz solve payload는 learner-facing이라 정답 키를 직접 주지 않습니다
- submit은 전 문항 응답 전에는 `422`
- report는 static coverage + dynamic learner memo를 함께 제공합니다

## Developer Notes

- 현재 accepted baseline은 `week 1` 기준입니다.
- `week 2+`는 같은 구조의 private data bundle이 추가로 필요합니다.
- SQLite fallback은 테스트/오프라인 개발용이고, 현재 canonical runtime은 PostgreSQL입니다.
- historical progress/handoff 문서는 보존되지만 현재 상태 판단 기준은 아닙니다.

## Docs

- Current state snapshot: [current_state_snapshot_2026-03-18.md](docs/current_state_snapshot_2026-03-18.md)
- Architecture: [architecture.md](docs/architecture.md)
- Baseline status: [local_week1_baseline_progress.md](docs/local_week1_baseline_progress.md)
- Deployment/data bundle: [deployment_runtime_bundle.md](docs/deployment_runtime_bundle.md)
- Documentation map: [documentation_map.md](docs/documentation_map.md)
