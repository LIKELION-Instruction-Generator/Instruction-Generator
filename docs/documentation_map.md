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

public repo에는 **실행과 현재 상태 이해에 필요한 문서만 포함**한다.

현재 public repo에서 추가로 참고 가능한 문서:

- `docs/llm_prompts.md`
  - runtime prompt single source
  - `src/stt_quiz_service/prompts.py`가 직접 읽는 파일

주의:
- 로컬에서 사용했던 상세 작업 로그, handoff 문서, historical prompt 문서는 public repo에 모두 포함하지 않을 수 있다.
- 실행과 현재 상태 판단은 canonical docs만으로 가능해야 한다.

## Historical / archived docs

historical / archived 문서는 로컬 작업 기록 기준으로 보존될 수 있지만, public repo에는 포함하지 않을 수 있다.

중요:
- public repo 기준으로는 historical 문서 부재가 실행 blocker가 되면 안 된다.
- 실행과 협업 재현에 필요한 정보는 canonical docs 또는 `docs/llm_prompts.md` 안에만 남긴다.

## Checklist docs

세부 체크리스트 문서는 public repo에서 생략될 수 있다.

주의:
- 제품 현재 상태 판단은 `docs/current_state_snapshot_2026-03-18.md`, `docs/architecture.md`, `docs/local_week1_baseline_progress.md`를 우선한다.

## 운영 원칙

1. 현재 상태를 설명할 때는 canonical docs만 업데이트한다.
2. 날짜가 붙은 prompt/handoff 문서는 historical로 보존한다.
3. 같은 내용을 여러 문서에 복제하지 않는다.
4. 다음 작업 우선순위는 `docs/roadmap_after_baseline_2026-03-17.md`에만 기록한다.
