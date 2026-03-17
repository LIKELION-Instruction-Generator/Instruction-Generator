import { getStrictFieldReadyCount } from "../../services/adapters/weekly";
import type { WeeklyQuizLearnerSet, WeeklyReport } from "../../types/api";

export function ReportMetricCards({
  quiz,
  report,
}: {
  quiz: WeeklyQuizLearnerSet;
  report: WeeklyReport;
}) {
  const strictFieldReadyCount = getStrictFieldReadyCount(quiz.items);

  return (
    <section className="grid gap-6 md:grid-cols-3">
      <MetricCard
        label="문항 규모"
        value={`${quiz.items.length}문항`}
        hint={`${quiz.corpus_ids.length}회차를 바탕으로 구성된 주간 묶음`}
      />
      <MetricCard
        label="주차 구성"
        value={`회차당 ${quiz.min_questions_per_corpus}문항`}
        hint="주간 단위로 고르게 복습할 수 있도록 정리했습니다"
      />
      <MetricCard
        label="근거 표시"
        value={`${strictFieldReadyCount}/${quiz.items.length}`}
        hint={report.notes[0] ?? "문항별 근거 정보가 함께 제공됩니다"}
      />
    </section>
  );
}

function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <article className="rounded-[28px] border border-orange-100 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-black tracking-tight text-slate-900">{value}</p>
      <p className="mt-3 text-xs font-semibold uppercase tracking-[0.2em] text-orange-500">
        {hint}
      </p>
    </article>
  );
}
