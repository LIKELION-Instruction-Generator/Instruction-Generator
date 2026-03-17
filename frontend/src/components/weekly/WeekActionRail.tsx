import { Link } from "react-router-dom";
import {
  getLearnerMemoReviewPoints,
  getWeeklyFallbackNote,
} from "../../services/adapters/weekly";
import { LearnerMemoCard } from "./LearnerMemoCard";
import type {
  WeeklyBundlePayload,
  WeeklyLearnerMemo,
  WeeklyQuizLearnerSet,
  WeeklyReport,
  WeeklySelection,
} from "../../types/api";

export function WeekActionRail({
  week,
  quiz,
  report,
  bundle,
  learnerMemo,
  memoError,
  memoLoading,
  onRetryMemo,
}: {
  week: WeeklySelection;
  quiz: WeeklyQuizLearnerSet;
  report: WeeklyReport;
  bundle: WeeklyBundlePayload;
  learnerMemo: WeeklyLearnerMemo | null;
  memoError?: string | null;
  memoLoading?: boolean;
  onRetryMemo?: () => void;
}) {
  const fallbackNote = getWeeklyFallbackNote(bundle.guide, report);
  const memoReviewPoints = getLearnerMemoReviewPoints(learnerMemo, bundle.guide, 3);
  const statItems = [
    { label: "학습 회차", value: `${week.corpus_ids.length}` },
    { label: "문항 수", value: `${quiz.items.length}` },
    { label: "주제 축", value: `${bundle.guide.topic_axes.length}` },
    { label: "복습 포인트", value: `${bundle.guide.review_points.length}` },
  ];

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] border border-slate-100 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
          학습 현황
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3">
          {statItems.map((item) => (
            <div
              className="rounded-[22px] border border-slate-100 bg-slate-50 px-4 py-4"
              key={item.label}
            >
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                {item.label}
              </p>
              <p className="mt-2 text-2xl font-black tracking-tight text-slate-900">
                {item.value}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-[32px] border border-orange-200 bg-[linear-gradient(160deg,rgba(255,237,213,0.9),rgba(255,255,255,0.96))] p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
          바로 이동
        </p>
        <h3 className="text-kr mt-3 text-2xl font-black tracking-tight text-slate-900">
          이번 주 학습 흐름을 바로 이어서 볼 수 있습니다
        </h3>
        <div className="mt-5 space-y-3">
          <Link
            className="flex items-center justify-between rounded-2xl bg-orange-500 px-4 py-4 text-sm font-bold text-white transition hover:bg-orange-600"
            to={`/weeks/${week.week_id}/quiz`}
          >
            퀴즈 보기
            <span>{quiz.items.length}문항</span>
          </Link>
          <Link
            className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-4 text-sm font-semibold text-slate-700 transition hover:border-orange-200 hover:text-orange-600"
            to={`/weeks/${week.week_id}/report`}
          >
            리포트 보기
            <span>{report.question_type_metrics.length}개 유형</span>
          </Link>
        </div>
      </section>

      <LearnerMemoCard
        compact
        error={memoError}
        fallbackNote={fallbackNote}
        learnerMemo={learnerMemo}
        loading={memoLoading}
        onRetry={onRetryMemo}
        reviewPoints={memoReviewPoints}
        weekId={week.week_id}
      />
    </div>
  );
}
