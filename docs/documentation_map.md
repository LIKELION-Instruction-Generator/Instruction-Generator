# Documentation Map

## 목적

현재 폴더 안 문서가 많고 날짜별 기록 문서가 섞여 있으므로, **어떤 문서가 현재 기준인지**를 단일하게 정리한다.

## Canonical docs

아래 문서만 현재 기준 문서로 본다.

1. `README.md`
   - GitHub / developer entrypoint
   - 서비스 소개, private data 정책, 실행 순서

2. `docs/current_state_snapshot_2026-03-18.md`
   - 현재 구현 상태 스냅샷
   - accepted baseline, 현재 API/runtime 상태 요약

3. `docs/architecture.md`
   - 현재 시스템 구조
   - weekly topic / guide / strict RAG quiz / report / frontend web app 관계

4. `docs/local_week1_baseline_progress.md`
   - current accepted baseline 상태
   - seed reuse 여부
   - acceptance 결과

5. `docs/roadmap_after_baseline_2026-03-17.md`
   - 프론트/백 정상화 이후 다음 단계
   - backlog 우선순위

6. `docs/deployment_runtime_bundle.md`
   - GitHub 코드와 private data bundle 분리 기준
   - 팀원 runtime 재현 절차

7. 원본 요구사항 문서
   - `과제명세서.md`
   - `NLP_Task2/README.md`

## Active implementation docs

현재 구현/마이그레이션 맥락에서 참조 가능한 문서:

- `docs/weekly_quiz_rag_langchain_migration_guide_2026-03-17.md`
  - quiz strict RAG 마이그레이션 기준
- `docs/quiz_submit_hardening_split_2026-03-17.md`
  - quiz submit hardening 단계의 문제 정의, 분업, 순서, 프롬프트
- `docs/learner_memo_and_report_refine_2026-03-17.md`
  - learner memo / report 정리 작업의 구현 배경 문서
  - 현재 API contract의 canonical source는 아니며, 최종 상태 판단은 `docs/current_state_snapshot_2026-03-18.md`와 `docs/architecture.md`를 우선한다
- `docs/local_cleanup_inventory_2026-03-18.md`
  - 로컬 정리 후보와 keep/delete 기준
- `docs/frontend_rebuild_checklist_2026-03-17.md`
  - frontend weekly web app 정렬 체크리스트
- `docs/frontend_rebuild_work_log_2026-03-17.md`
  - frontend 작업 로그

## Historical / archived docs

아래 문서는 보존은 하지만 **현재 기준 문서가 아니다**.

- `docs/runpod_handoff_2026-03-17.md`
  - historical handoff
- `docs/server_prompt_weekly_quiz_rag_2026-03-17.md`
  - historical execution prompt
- `docs/server_prompt_weekly_quiz_grounded_quality_refine_2026-03-17.md`
  - historical execution prompt
- `artifacts/runpod_fetch/gpu_backup_20260317/progress.md`
  - Runpod historical progress
- `artifacts/runpod_fetch/server_work_20260317/progress.md`
  - Runpod historical progress
- `docs/error-report.md`
  - incident archive

## Checklist docs

`docs/checklists/` 아래 문서는 세부 구현 단계별 체크리스트다.

주의:
- 이 체크리스트들은 현재 상태를 완전히 대표하지 않을 수 있다.
- 제품 현재 상태 판단은 `docs/current_state_snapshot_2026-03-18.md`, `docs/architecture.md`, `docs/local_week1_baseline_progress.md`를 우선한다.
- `docs/checklists/seeded_baseline_test_progress_2026-03-17.md`는 테스트 보조 기록이며, baseline의 canonical 진행 문서는 아니다.

## 운영 원칙

1. 현재 상태를 설명할 때는 canonical docs만 업데이트한다.
2. 날짜가 붙은 prompt/handoff 문서는 historical로 보존한다.
3. 같은 내용을 여러 문서에 복제하지 않는다.
4. 다음 작업 우선순위는 `docs/roadmap_after_baseline_2026-03-17.md`에만 기록한다.
