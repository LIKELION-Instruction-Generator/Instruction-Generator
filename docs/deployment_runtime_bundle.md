# Deployment Runtime Bundle

## 목적

코드는 GitHub에 올리고, private 데이터는 별도 번들로 공유해도 **현재 로컬과 동일한 week 1 서비스 표면**이 뜨도록 기준을 고정한다.

현재 기준 서비스 표면:
- `GET /weeks`
- `GET /weekly-bundle/{week_id}`
- `GET /weekly-quiz/{week_id}` (learner-facing, answer key 비노출)
- `POST /weekly-quiz/{week_id}/submit` (score / correct_count / results / learner_memo)
- `GET /weekly-quiz/{week_id}/latest-submission`
- `GET /weekly-quiz/{week_id}/attempts/{attempt_id}`
- `GET /weekly-report/{week_id}`
- React frontend (`hub / quiz / report`)

## 배포 전략

### GitHub에 올릴 것
- `src/`
- `frontend/` 소스 (`node_modules`, `dist` 제외)
- `scripts/`
- `tests/`
- `docs/`
- `pyproject.toml`
- `frontend/package.json`
- `frontend/package-lock.json`
- `.env.example`

### GitHub에 올리지 않을 것
- private lecture data
- accepted weekly artifacts
- local databases
- node_modules / dist / 가상환경
- Runpod fetch / 실험 로그

## 현재 runtime에 필요한 최소 데이터

### 필수
현재 week 1 서비스 실행에 실제로 필요한 private 데이터는 아래다.

1. curriculum
- `NLP_Task2/강의 커리큘럼.csv`

2. prepared corpus JSON (week 1만)
- `artifacts/preprocessed/2026-02-02.json`
- `artifacts/preprocessed/2026-02-03.json`
- `artifacts/preprocessed/2026-02-04.json`
- `artifacts/preprocessed/2026-02-05.json`
- `artifacts/preprocessed/2026-02-06.json`

3. accepted weekly artifacts
- `artifacts/pipeline_state/weekly_1_topic_set.json`
- `artifacts/pipeline_state/weekly_1_guide.json`
- `artifacts/pipeline_state/weekly_1_quiz.json`
- `artifacts/pipeline_state/weekly_1_report.json`

### 선택
아래는 현재 week 1 서비스 구동에는 필요 없지만, 재생성/확장/검증에 유용하다.

- `artifacts/runpod_fetch/gpu_backup_20260317/daily_term_candidates_export.jsonl`
  - upstream seed 재사용 또는 재검증 시 필요
- `artifacts/runpod_fetch/gpu_backup_20260317/weekly_1_topic_set.json`
  - historical seed 비교 시 필요
- `NLP_Task2/강의 스크립트/`
  - raw transcript 기반 재전처리나 full pipeline 실험 시 필요
- `artifacts/preprocessed/*.txt`
  - 사람이 inspection할 때 유용하지만, week 1 accepted sync 자체는 `.json`만 사용
- `artifacts/stitch/`
  - 디자인 참고 자료

### 현재 runtime에 불필요
현재 week 1 서비스 구동만 놓고 보면 아래는 필요 없다.

- `artifacts/runpod_fetch/week1/`
- `artifacts/runpod_fetch/server_work_20260317/`
- `artifacts/runpod_fetch/gpu_backup_20260317/progress.md`
- root의 임시 DB/로그 파일
- frontend build 결과물 (`frontend/dist`)
- `frontend/node_modules`

## 권장 데이터 번들 구조

팀원에게는 아래 상대 경로를 유지한 채로 zip/tar로 전달하는 것이 가장 단순하다.

```text
runtime-data-bundle/
  NLP_Task2/
    강의 커리큘럼.csv
  artifacts/
    preprocessed/
      2026-02-02.json
      2026-02-03.json
      2026-02-04.json
      2026-02-05.json
      2026-02-06.json
    pipeline_state/
      weekly_1_topic_set.json
      weekly_1_guide.json
      weekly_1_quiz.json
      weekly_1_report.json
```

권장 사용 방식:
- GitHub clone 후 repo root에 위 경로 그대로 덮어쓰기/복사
- 경로를 바꾸지 않으면 현재 스크립트를 수정할 필요가 없다
- zip을 푼 뒤 `runtime-data-bundle-.../` 폴더 자체를 두는 것이 아니라, 그 안의 `NLP_Task2/` 와 `artifacts/` 디렉터리를 repo root로 복사해야 한다

## 환경변수

### 기본 runtime에 필수
- 경로를 문서 그대로 유지하면 추가 필수 env는 없다

### 권장
- `STT_QUIZ_DATABASE_URL`
- `STT_QUIZ_SYNC_ACCEPTED_WEEKLY_BASELINE=true`
- `STT_QUIZ_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`

### generation / LLM 경로에서만 필요
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY` 또는 `GEMINI_API_KEY`

### tracing 선택
- `LANGSMITH_TRACING=true`
- `LANGSMITH_PROJECT=stt-quiz-service`
- `LANGSMITH_ENDPOINT=https://api.smith.langchain.com`
- `LANGSMITH_API_KEY=...`

## 팀원 실행 순서

1. 코드 clone
2. private runtime data bundle을 repo root에 복사
3. Python 환경 준비
   - `python3 -m venv .venv_quizsvc`
   - `./.venv_quizsvc/bin/python -m pip install --upgrade pip setuptools wheel`
   - `./.venv_quizsvc/bin/pip install -e ".[dev]"`
4. frontend 환경 준비
   - `cd frontend && npm install`
5. runtime data 확인
   - `./.venv_quizsvc/bin/python scripts/check_runtime_data_bundle.py --week-id 1`
6. API 실행
  - `./scripts/run_api.sh`
  - 동작:
    - `STT_QUIZ_DATABASE_URL`이 PostgreSQL이면 `start_postgres.sh` 선실행
    - accepted `week 1` read model sync
    - uvicorn 실행
7. frontend 실행
  - `cd frontend && npm run dev`

주의:
- `zsh`에서는 `.[dev]`를 glob으로 해석할 수 있으므로 `pip install -e ".[dev]"`처럼 따옴표를 유지한다.
- `No module named 'dotenv'`는 editable install이 완료되지 않았다는 뜻이다. 가상환경을 새로 만든 뒤 다시 설치한다.
- `Failed to build 'pyyaml'`가 보이면 최신 저장소 기준으로 다시 clone/pull 하고, 가상환경을 재생성한 뒤 재설치한다. 현재 저장소는 `PyYAML>=6.0.2`를 직접 고정한다.

## 검증 기준

아래가 통과하면 현재 로컬과 같은 수준으로 서비스가 올라온 것이다.

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/weeks
curl http://127.0.0.1:8000/weekly-bundle/1
curl http://127.0.0.1:8000/weekly-quiz/1
curl http://127.0.0.1:8000/weekly-report/1
```

브라우저:
- `http://127.0.0.1:5173/weeks/1/hub`
- `http://127.0.0.1:5173/weeks/1/quiz`
- `http://127.0.0.1:5173/weeks/1/report`

## 메모

- 현재 accepted baseline은 week 1만 보장한다.
- week 2+를 서비스하려면 같은 구조의 `prepared corpus json + weekly artifacts`를 추가로 배포해야 한다.
- 최신 제출 결과는 DB에 저장되므로, DB는 runtime state이고 data bundle에는 포함하지 않는다.
- `check_runtime_data_bundle.py`는 curriculum + prepared corpus json + accepted artifacts 존재 여부만 검증하며, API key는 검사하지 않는다.
