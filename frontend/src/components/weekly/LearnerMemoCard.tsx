import { Link } from "react-router-dom";
import type { WeeklyLearnerMemo } from "../../types/api";

export function LearnerMemoCard({
  compact = false,
  error,
  fallbackNote,
  learnerMemo,
  loading,
  onRetry,
  reviewPoints,
  weekId,
}: {
  compact?: boolean;
  error?: string | null;
  fallbackNote: string;
  learnerMemo: WeeklyLearnerMemo | null;
  loading?: boolean;
  onRetry?: () => void;
  reviewPoints: string[];
  weekId: string;
}) {
  const title = learnerMemo?.headline ?? "이번 주 메모";
  const summary = learnerMemo?.summary ?? fallbackNote;
  const points = learnerMemo?.recommended_review_points.length
    ? learnerMemo.recommended_review_points
    : reviewPoints;
  const visiblePoints = points.slice(0, compact ? 2 : 3);
  const cardPadding = compact ? "p-5" : "p-6";

  return (
    <section className={`rounded-[32px] border border-slate-100 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.08)] ${cardPadding}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
            이번 주 메모
          </p>
          <h3 className="text-kr mt-2 text-2xl font-black tracking-tight text-slate-900">
            {loading ? "최근 제출을 바탕으로 메모를 정리하는 중입니다" : title}
          </h3>
        </div>
        {learnerMemo?.status === "all_correct" ? (
          <span className="rounded-full bg-emerald-100 px-3 py-2 text-xs font-semibold text-emerald-700">
            복습 완료
          </span>
        ) : null}
        {learnerMemo?.status === "ready" ? (
          <span className="rounded-full bg-orange-50 px-3 py-2 text-xs font-semibold text-orange-600">
            최근 제출 기준
          </span>
        ) : null}
      </div>

      <p className="text-kr mt-4 text-sm leading-6 text-slate-600">
        {loading
          ? "가장 최근 제출과 이번 주 가이드를 함께 읽고, 우선 복습할 포인트를 정리하고 있습니다."
          : summary}
      </p>

      {error ? (
        <div className="mt-4 rounded-[20px] border border-orange-100 bg-orange-50/70 px-4 py-4">
          <p className="text-kr text-sm leading-6 text-slate-600">
            동적 학습 메모를 불러오지 못해 기본 메모를 대신 보여주고 있습니다.
          </p>
          {onRetry ? (
            <button
              className="mt-3 rounded-full border border-orange-200 bg-white px-4 py-2 text-sm font-semibold text-orange-700 transition hover:border-orange-300"
              onClick={onRetry}
              type="button"
            >
              다시 시도
            </button>
          ) : null}
        </div>
      ) : null}

      {!loading && learnerMemo?.status === "ready" && learnerMemo.focus_topics.length > 0 ? (
        <div className="mt-5">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
            오답 집중 주제
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {learnerMemo.focus_topics.slice(0, compact ? 2 : 3).map((topic) => (
              <span
                className="rounded-full border border-red-100 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700"
                key={topic.label}
              >
                {topic.label} · {topic.wrong_count}개
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {!loading && learnerMemo?.status === "ready" && learnerMemo.focus_dates.length > 0 ? (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
            다시 볼 날짜
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {learnerMemo.focus_dates.slice(0, compact ? 2 : 3).map((dateItem) => (
              <span
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700"
                key={dateItem.source_date}
              >
                {dateItem.source_date} · {dateItem.wrong_count}개
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {visiblePoints.length > 0 ? (
        <div className="mt-5">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
            우선 복습할 포인트
          </p>
          <div className="mt-3 space-y-2">
            {visiblePoints.map((point) => (
              <div
                className="rounded-[18px] border border-slate-100 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700"
                key={point}
              >
                {point}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {!loading && learnerMemo?.status === "no_submission" ? (
        <div className="mt-5">
          <Link
            className="inline-flex rounded-full bg-orange-500 px-4 py-2 text-sm font-bold text-white transition hover:bg-orange-600"
            to={`/weeks/${weekId}/quiz`}
          >
            퀴즈 풀기
          </Link>
        </div>
      ) : null}
    </section>
  );
}
