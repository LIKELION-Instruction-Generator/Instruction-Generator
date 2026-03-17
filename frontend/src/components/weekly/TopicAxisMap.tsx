import { getTopicQuestionCount } from "../../services/adapters/weekly";
import type { TopicAxis, WeeklyQuizLearnerItem } from "../../types/api";

export function TopicAxisMap({
  topicAxes,
  quizItems,
}: {
  topicAxes: TopicAxis[];
  quizItems: WeeklyQuizLearnerItem[];
}) {
  if (!topicAxes.length) {
    return (
      <div className="rounded-[28px] border border-dashed border-slate-200 bg-slate-50 px-5 py-6">
        <p className="text-sm font-semibold text-slate-500">
          아직 정리된 주제 축이 없습니다.
        </p>
      </div>
    );
  }

  return (
    <div className="relative flex h-full min-h-[520px] items-center overflow-hidden rounded-[28px] border border-slate-100 bg-slate-50 p-4 sm:p-6">
      <div className="absolute inset-0 opacity-50 [background-image:radial-gradient(circle_at_1px_1px,rgba(249,115,22,0.18)_1px,transparent_0)] [background-size:18px_18px]" />
      <div className="relative grid w-full self-center items-stretch gap-4 lg:grid-cols-2">
        {topicAxes.map((axis, index) => (
          <article
            className={`flex min-h-[360px] rounded-[24px] border border-orange-200 bg-white p-6 shadow-[0_16px_40px_rgba(15,23,42,0.08)] ${
              topicAxes.length % 2 === 1 && index === topicAxes.length - 1 ? "lg:col-span-2" : ""
            }`}
            key={axis.label}
          >
            <AxisCard axis={axis} quizItems={quizItems} />
          </article>
        ))}
      </div>
    </div>
  );
}

function AxisCard({
  axis,
  quizItems,
}: {
  axis: TopicAxis;
  quizItems: WeeklyQuizLearnerItem[];
}) {
  const questionCount = getTopicQuestionCount(quizItems, axis.label);

  return (
    <div className="flex h-full flex-col justify-between">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-orange-500">
            학습 축
          </p>
          <p className="text-kr mt-2 text-[1.05rem] font-bold leading-7 text-slate-900">{axis.label}</p>
          <div className="mt-1 space-y-1 text-xs leading-5 text-slate-400">
            <p>
              {axis.source_corpus_ids.length}회차 · {questionCount}문항
            </p>
            {axis.source_corpus_ids.length > 0 ? (
              <div className="flex flex-wrap gap-x-2 gap-y-1">
                {axis.source_corpus_ids.map((sourceId) => (
                  <span className="whitespace-nowrap" key={`${axis.label}-${sourceId}`}>
                    {sourceId}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </div>
        <span className="shrink-0 rounded-full bg-orange-50 px-2 py-1 text-[11px] font-semibold text-orange-600">
          {axis.supporting_terms.length}개 키워드
        </span>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {axis.supporting_terms.slice(0, 5).map((term) => (
          <span
            className="rounded-full border border-slate-200 px-2 py-1 text-xs text-slate-600"
            key={`${axis.label}-${term}`}
          >
            {term}
          </span>
        ))}
      </div>
    </div>
  );
}
