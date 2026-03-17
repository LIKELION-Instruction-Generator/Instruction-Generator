export function QuestionProgress({
  currentIndex,
  total,
  contractLabel,
  answeredCount,
  unansweredCount,
  submitted = false,
  score,
  correctCount,
}: {
  currentIndex: number;
  total: number;
  contractLabel: string;
  answeredCount: number;
  unansweredCount: number;
  submitted?: boolean;
  score?: number;
  correctCount?: number;
}) {
  const progress = total > 0 ? Math.round(((currentIndex + 1) / total) * 100) : 0;

  return (
    <section className="rounded-[28px] border border-slate-100 bg-white px-6 py-5 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
            학습 진행
          </p>
          <h2 className="mt-2 text-2xl font-black tracking-tight text-slate-900">
            {total}문항 중 {currentIndex + 1}번째 문제
          </h2>
        </div>
        <div className="flex gap-2 text-xs font-semibold text-slate-500">
          <span className="rounded-full bg-orange-50 px-3 py-2 text-orange-600">
            {submitted ? `${correctCount ?? 0}개 정답` : `${answeredCount}개 응답`}
          </span>
          <span className="rounded-full bg-slate-100 px-3 py-2">
            {submitted
              ? `${score ?? 0}점`
              : unansweredCount > 0
                ? `${unansweredCount}개 남음`
                : contractLabel}
          </span>
        </div>
      </div>
      <div className="mt-4 h-3 rounded-full bg-slate-200">
        <div className="h-3 rounded-full bg-orange-500" style={{ width: `${progress}%` }} />
      </div>
    </section>
  );
}
