import {
  getRecommendedReviewItems,
  getTopicCoverageShare,
} from "../../services/adapters/weekly";
import type {
  WeeklyGuide,
  WeeklyLearnerMemo,
  WeeklyQuizLearnerSet,
  WeeklyQuizSubmissionDetailResponse,
  WeeklyReport,
} from "../../types/api";

export function TopicCoveragePanel({
  guide,
  learnerMemo,
  quiz,
  submission,
  report,
}: {
  guide: WeeklyGuide;
  learnerMemo?: WeeklyLearnerMemo | null;
  quiz: WeeklyQuizLearnerSet;
  submission?: WeeklyQuizSubmissionDetailResponse | null;
  report: WeeklyReport;
}) {
  const coverageShare = getTopicCoverageShare(report, quiz.items.length);
  const reviewItems = getRecommendedReviewItems(guide, report, learnerMemo, submission);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-[32px] border border-orange-100 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
          주제 커버리지
        </p>
        <div className="mt-5 space-y-5">
          {coverageShare.map((coverage) => (
            <article key={coverage.topic_axis_label}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{coverage.topic_axis_label}</p>
                  <p className="mt-1 text-xs text-slate-400">
                    {coverage.supporting_terms.slice(0, 4).join(" · ")}
                  </p>
                </div>
                <span className="text-sm font-bold text-orange-600">
                  {coverage.question_count} · {coverage.share}%
                </span>
              </div>
              <div className="mt-3 h-3 rounded-full bg-slate-100">
                <div
                  className="h-3 rounded-full bg-orange-500"
                  style={{ width: `${coverage.share}%` }}
                />
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-[32px] border border-orange-100 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
          추천 복습 순서
        </p>
        <div className="mt-5 space-y-4">
          {reviewItems.map((item) => (
            <article
              className="rounded-[24px] border border-slate-100 bg-slate-50 px-4 py-4"
              key={`${item.meta}-${item.title}`}
            >
              <p className="text-sm font-semibold leading-6 text-slate-900">{item.title}</p>
              <p className="mt-1 text-xs text-slate-400">{item.meta}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
