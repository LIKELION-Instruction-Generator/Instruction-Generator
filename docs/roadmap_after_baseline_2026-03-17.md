# Roadmap After Baseline (2026-03-17)

## 기준 상태

현재 기준은 `week 1 accepted seeded baseline`이다.

이미 닫힌 것:
- 전처리
- weekly topic seed 고정
- strict RAG weekly quiz baseline
- week 1 guide/quiz/report acceptance
- frontend weekly web app 기본 연결
- quiz submit / score / review flow
- latest submission 기반 learner memo / 오답 리뷰

## 현재 안정화 트랙

남아 있는 안정화 작업은 주로 frontend presentation 쪽이다. backend runtime stabilization은 이미 닫혔다.

### 1. Frontend presentation stabilization

목표:
- 현재 weekly web app을 실제 제품 화면 수준으로 정리

핵심 작업:
- 한국어 폰트/레이아웃 안정화
- `/weeks` 메타 대신 bundle 중심 display copy 재구성
- hub / quiz / report product-facing copy 정리
- runtime QA

완료 기준:
- `hub / quiz / report`가 live API 기준으로 안정적으로 렌더링
- 긴 한국어 텍스트가 깨지지 않음
- coverage report 의미가 UI에 명확히 드러남

### 2. Backend runtime stabilization

목표:
- 프론트가 실서비스처럼 동적으로 붙을 수 있는 API 상태 확보

핵심 작업:
- `PostgreSQL + FastAPI` 실행 안정화
- `/health`, `/weeks`, `/weekly-bundle/{week_id}` 검증
- frontend에서 필요한 metadata mismatch 정리

완료 기준:
- 로컬/개발 환경에서 weekly web app을 안정적으로 띄울 수 있음
- accepted week 1 bundle + quiz submit/review + dynamic learner memo 흐름이 안정적임

현재 상태:
- 완료
- 현재 backend는 `/health`, `/weeks`, `/weekly-bundle/{week_id}` 외에도 learner-facing weekly quiz, submit, latest submission review, dynamic learner memo report를 제공한다

## Frontend / Backend 안정화 이후 우선순위

아래부터가 실제 기능 확장 backlog다.

### 3. Learner performance expansion

목표:
- latest submission 중심 피드백을 넘어, 실제 learner performance report로 확장

핵심 작업:
- multi-attempt 누적 성과 계산
- corpus/topic/profile별 trend 집계
- learner report API 확장
- frontend 성과/약점 시각화
- latest submission 피드백과 누적 performance를 분리

완료 기준:
- report가 latest submission 요약을 넘어 누적 learner result를 반영
- 동일 주차 재시도 변화량까지 설명 가능

### 4. Week 2+ expansion

목표:
- week 1 기준을 다른 주차에도 적용

핵심 작업:
- week 2, 3 accepted baseline 생성
- acceptance check 자동화
- 품질 편차 점검

완료 기준:
- week 1만 맞는 특수 경로가 아니라 전체 주차로 일반화

## 현재 backlog

### Backend
- multi-attempt learner performance endpoint
- `/weekly-bundle/{week_id}`에 필요한 display metadata 정리 여부 결정

### Frontend
- font/layout stabilization
- copy cleanup
- live API QA
- hub/report 섹션 병합 및 wrong-answer review polish

### Pipeline
- distractor grounding 추가 개선
- concept map 제품화
- acceptance check script 자동화
