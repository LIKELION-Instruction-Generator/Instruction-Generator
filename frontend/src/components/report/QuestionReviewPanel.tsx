import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { WeeklyQuizReviewResult } from "../../types/api";

export function QuestionReviewPanel({
  currentPage,
  error,
  hasSubmission,
  items,
  loading,
  onNextPage,
  onPreviousPage,
  onRetry,
  totalPages,
  weekId,
  wrongItemCount,
}: {
  currentPage: number;
  error: string | null;
  hasSubmission: boolean;
  items: WeeklyQuizReviewResult[];
  loading: boolean;
  onNextPage: () => void;
  onPreviousPage: () => void;
  onRetry: () => void;
  totalPages: number;
  weekId: string;
  wrongItemCount: number;
}) {
  return (
    <section className="rounded-[32px] border border-orange-100 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
            오답 다시 보기
          </p>
          <h3 className="mt-2 text-2xl font-black tracking-tight text-slate-900">
            최근 제출에서 다시 볼 문제
          </h3>
        </div>
        {hasSubmission && wrongItemCount > 0 ? (
          <div className="flex items-center gap-2 text-xs font-semibold">
            <button
              className="rounded-full border border-slate-200 px-3 py-2 text-slate-600 transition hover:border-orange-200 hover:text-orange-600 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={currentPage === 0}
              onClick={onPreviousPage}
              type="button"
            >
              이전
            </button>
            <span className="rounded-full bg-slate-100 px-3 py-2 text-slate-600">
              {currentPage + 1} / {totalPages}
            </span>
            <button
              className="rounded-full border border-slate-200 px-3 py-2 text-slate-600 transition hover:border-orange-200 hover:text-orange-600 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={currentPage >= totalPages - 1}
              onClick={onNextPage}
              type="button"
            >
              다음
            </button>
          </div>
        ) : null}
      </div>

      {loading ? (
        <StateCard
          description="가장 최근 제출 결과에서 다시 볼 문제를 정리하고 있습니다."
          eyebrow="리뷰 준비 중"
          title="오답 리뷰를 불러오는 중입니다"
        />
      ) : null}

      {!loading && error ? (
        <div className="mt-6 rounded-[24px] border border-red-100 bg-red-50 px-5 py-5">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-red-500">
            리뷰 불러오기 실패
          </p>
          <p className="text-kr mt-3 text-sm leading-6 text-slate-700">{error}</p>
          <button
            className="mt-4 rounded-full bg-orange-500 px-4 py-2 text-sm font-bold text-white transition hover:bg-orange-600"
            onClick={onRetry}
            type="button"
          >
            다시 시도
          </button>
        </div>
      ) : null}

      {!loading && !error && !hasSubmission ? (
        <StateCard
          action={
            <Link
              className="inline-flex rounded-full bg-orange-500 px-4 py-2 text-sm font-bold text-white transition hover:bg-orange-600"
              to={`/weeks/${weekId}/quiz`}
            >
              퀴즈 풀기
            </Link>
          }
          description="오답 리뷰는 가장 최근에 제출한 퀴즈 결과를 기준으로 만들어집니다."
          eyebrow="제출 이력 없음"
          title="아직 제출한 퀴즈가 없습니다"
        />
      ) : null}

      {!loading && !error && hasSubmission && wrongItemCount === 0 ? (
        <StateCard
          badge="복습 완료"
          description="가장 최근 제출에서 모든 문제를 맞혔습니다. 이번 주 핵심 개념을 안정적으로 이해하고 있습니다."
          eyebrow="오답 0개"
          title="모든 문제를 맞혔습니다"
        />
      ) : null}

      {!loading && !error && hasSubmission && wrongItemCount > 0 ? (
        <div className="mt-6 space-y-5">
          {items.map((item, index) => (
            <article
              className="rounded-[24px] border border-slate-100 bg-slate-50 px-5 py-5"
              key={item.item_id}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-orange-500">
                    오답 {String(currentPage * 2 + index + 1).padStart(2, "0")}
                  </p>
                  <h4 className="text-kr mt-2 text-lg font-bold leading-7 text-slate-900">
                    {item.question}
                  </h4>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-600">
                    강의 날짜 {item.source_date}
                  </span>
                  <span className="rounded-full bg-red-100 px-3 py-2 text-xs font-semibold text-red-700">
                    다시 확인 필요
                  </span>
                </div>
              </div>

              <div className="mt-5 grid gap-3">
                {item.options.map((option, optionIndex) => (
                  <ReviewOptionRow
                    correctOptionIndex={item.correct_option_index}
                    key={`${item.item_id}-${optionIndex}`}
                    option={option}
                    optionIndex={optionIndex}
                    selectedOptionIndex={item.selected_option_index}
                  />
                ))}
              </div>

              {item.selected_option_index === null ? (
                <div className="mt-4 rounded-[20px] border border-amber-100 bg-amber-50 px-4 py-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-600">
                    제출 기록
                  </p>
                  <p className="text-kr mt-2 text-sm leading-6 text-slate-700">
                    이 문항은 제출 시 미응답으로 기록되었습니다.
                  </p>
                </div>
              ) : null}

              <div className="mt-4 rounded-[20px] border border-red-100 bg-white px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-red-500">
                  해설
                </p>
                <p className="text-kr mt-2 text-sm leading-6 text-slate-700">{item.explanation}</p>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function StateCard({
  action,
  badge,
  description,
  eyebrow,
  title,
}: {
  action?: ReactNode;
  badge?: string;
  description: string;
  eyebrow: string;
  title: string;
}) {
  return (
    <div className="mt-6 rounded-[24px] border border-slate-100 bg-slate-50 px-5 py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-orange-500">
            {eyebrow}
          </p>
          <h4 className="mt-2 text-xl font-black tracking-tight text-slate-900">{title}</h4>
        </div>
        {badge ? (
          <span className="rounded-full bg-emerald-100 px-3 py-2 text-xs font-semibold text-emerald-700">
            {badge}
          </span>
        ) : null}
      </div>
      <p className="text-kr mt-3 text-sm leading-6 text-slate-600">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

function ReviewOptionRow({
  correctOptionIndex,
  option,
  optionIndex,
  selectedOptionIndex,
}: {
  correctOptionIndex: number;
  option: string;
  optionIndex: number;
  selectedOptionIndex: number | null;
}) {
  const isCorrect = correctOptionIndex === optionIndex;
  const isSelected = selectedOptionIndex === optionIndex;

  let toneClassName = "border-slate-200 bg-white text-slate-800";
  if (isCorrect) {
    toneClassName = "border-green-200 bg-green-50 text-green-900";
  } else if (isSelected) {
    toneClassName = "border-red-200 bg-red-50 text-red-900";
  }

  const badges: string[] = [];
  if (isSelected) {
    badges.push("내가 고른 답");
  }
  if (isCorrect) {
    badges.push("정답");
  }

  return (
    <div className={`rounded-[20px] border px-4 py-4 ${toneClassName}`}>
      <div className="flex items-start gap-4">
        <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-current text-xs font-bold">
          {String.fromCharCode(65 + optionIndex)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-kr text-sm font-semibold leading-6">{option}</p>
          {badges.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {badges.map((badge) => (
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                    badge === "정답"
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-700"
                  }`}
                  key={`${optionIndex}-${badge}`}
                >
                  {badge}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
