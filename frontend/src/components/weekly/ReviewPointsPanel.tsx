import type { TopicAxis } from "../../types/api";

export function ReviewPointsPanel({
  reviewPoints,
  topicAxes,
}: {
  reviewPoints: string[];
  topicAxes: TopicAxis[];
}) {
  return (
    <section className="rounded-[32px] border border-orange-100 bg-white p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
        복습 포인트
      </p>
      <div className="mt-5 space-y-3">
        {reviewPoints.length ? (
          reviewPoints.map((reviewPoint, index) => (
            <article
              className="rounded-[24px] border border-slate-100 bg-slate-50 px-4 py-4"
              key={`${reviewPoint}-${index}`}
            >
              <div className="flex items-start gap-3">
                <div className="mt-1 h-5 w-5 rounded-full border-2 border-orange-300 bg-white" />
                <div>
                  <p className="text-sm font-semibold leading-6 text-slate-800">{reviewPoint}</p>
                  <p className="mt-1 text-xs text-slate-400">
                    {topicAxes[index % Math.max(topicAxes.length, 1)]?.label ?? "Weekly review"}
                  </p>
                </div>
              </div>
            </article>
          ))
        ) : (
          <p className="rounded-[24px] border border-dashed border-slate-200 px-4 py-6 text-sm text-slate-500">
            이번 주 가이드에 복습 포인트가 아직 정리되지 않았습니다.
          </p>
        )}
      </div>
    </section>
  );
}
