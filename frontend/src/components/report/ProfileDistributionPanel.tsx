import { getQuestionTypeShare, getProfileLabel } from "../../services/adapters/weekly";
import type { WeeklyQuizLearnerSet, WeeklyReport } from "../../types/api";

export function ProfileDistributionPanel({
  quiz,
  report,
}: {
  quiz: WeeklyQuizLearnerSet;
  report: WeeklyReport;
}) {
  const metrics = getQuestionTypeShare(report.question_type_metrics, quiz.items.length);

  return (
    <section className="rounded-[32px] border border-orange-100 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
        문항 유형 분포
      </p>
      <div className="mt-5 space-y-5">
        {metrics.map((metric) => (
          <article key={metric.question_profile}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-semibold text-slate-800">
                {getProfileLabel(metric.question_profile)}
              </span>
              <span className="font-bold text-orange-600">
                {metric.question_count} questions · {metric.share}%
              </span>
            </div>
            <div className="mt-3 h-3 rounded-full bg-slate-100">
              <div
                className="h-3 rounded-full bg-orange-500"
                style={{ width: `${metric.share}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-slate-400">
              {metric.covered_topic_axes.join(" · ")}
            </p>
          </article>
        ))}
      </div>
      {report.mismatched_axis_item_count ? (
        <p className="mt-6 rounded-[20px] border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          {report.mismatched_axis_item_count} quiz items do not align cleanly with the recorded
          topic-axis mapping.
        </p>
      ) : null}
    </section>
  );
}
