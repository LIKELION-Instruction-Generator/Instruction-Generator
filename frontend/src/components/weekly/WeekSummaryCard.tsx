import {
  formatWeekLabel,
  formatWeekRange,
  getGuideLeadText,
  getTopicAxisPreviewLabels,
} from "../../services/adapters/weekly";
import { TopicAxisMap } from "./TopicAxisMap";
import type {
  WeeklyGuide,
  WeeklyQuizLearnerSet,
  WeeklySelection,
} from "../../types/api";

export function WeekSummaryCard({
  week,
  guide,
  quiz,
  topicAxes,
  minHeight,
}: {
  week: WeeklySelection;
  guide: WeeklyGuide;
  quiz: WeeklyQuizLearnerSet;
  topicAxes: WeeklyGuide["topic_axes"];
  minHeight?: number | null;
}) {
  const topicLabels = getTopicAxisPreviewLabels(guide.topic_axes, 3);
  const guideSummary = getGuideLeadText(guide.learning_paragraph, 2);
  const briefGuideSummary = getGuideLeadText(guide.learning_paragraph, 1);
  const firstReviewPoint =
    guide.review_points[0] ?? "이번 주 핵심 개념을 순서대로 다시 점검해 보세요.";

  return (
    <section
      className="flex h-full flex-col overflow-hidden rounded-[32px] border border-orange-100 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.08)]"
      style={minHeight ? { minHeight: `${minHeight}px` } : undefined}
    >
      <div className="relative overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.28),_transparent_34%),linear-gradient(135deg,_#f97316,_#7c2d12)] px-8 py-10 text-white">
        <div className="absolute inset-0 opacity-20 [background-image:radial-gradient(circle_at_1px_1px,white_1px,transparent_0)] [background-size:18px_18px]" />
        <div className="relative">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-orange-100">
            {formatWeekLabel(week)} · {formatWeekRange(week.dates)}
          </p>
          <h2 className="text-kr mt-3 max-w-3xl text-[clamp(1.9rem,4vw,2.8rem)] font-black leading-[1.25] tracking-tight">
            이번 주 핵심 주제
          </h2>
          <p className="text-kr mt-3 max-w-3xl text-sm leading-7 text-orange-50">
            {guideSummary}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {topicLabels.map((label) => (
              <span
                className="rounded-full border border-white/30 bg-white/10 px-3 py-2 text-xs font-semibold text-white/90"
                key={label}
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-1 flex-col px-8 py-8">
        <div className="grid gap-3 lg:grid-cols-3">
          <StatPill label="학습 회차" value={`${week.corpus_ids.length}`} />
          <StatPill label="문항 수" value={`${quiz.items.length}`} />
          <StatPill label="복습 포인트" value={`${guide.review_points.length}`} />
        </div>
        <div className="mt-6 grid gap-3">
          <MetaRow
            label="주요 주제"
            value={topicLabels.join(" / ") || "이번 주 핵심 주제가 아직 정리되지 않았습니다."}
          />
          <MetaRow label="가장 먼저 볼 포인트" value={firstReviewPoint} />
          <MetaRow label="이번 주 정리" value={briefGuideSummary} />
        </div>

        <div className="mt-8 flex flex-1 flex-col border-t border-slate-100 pt-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
                핵심 주제 흐름
              </p>
              <h3 className="text-kr mt-2 text-2xl font-black tracking-tight text-slate-900">
                이번 주 학습 축과 키워드
              </h3>
            </div>
            <p className="rounded-full bg-orange-50 px-3 py-2 text-xs font-semibold text-orange-600">
              {topicAxes.length}개 축
            </p>
          </div>
          <p className="text-kr mt-3 text-sm leading-6 text-slate-500">
            주제 축별로 포함 회차와 핵심 키워드를 바로 확인할 수 있도록 한 섹션으로 정리했습니다.
          </p>
          <div className="mt-5 flex-1">
            <TopicAxisMap quizItems={quiz.items} topicAxes={topicAxes} />
          </div>
        </div>
      </div>
    </section>
  );
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[24px] border border-slate-100 bg-slate-50 px-4 py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{label}</p>
      <p className="mt-3 text-2xl font-black tracking-tight text-slate-900">{value}</p>
    </div>
  );
}

function MetaRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[22px] border border-slate-100 bg-white px-5 py-4">
      <div className="grid gap-3 sm:grid-cols-[140px_minmax(0,1fr)] sm:items-start sm:gap-4">
        <div className="flex items-center">
          <span className="inline-flex rounded-full bg-slate-100 px-3 py-1.5 text-[11px] font-semibold tracking-[0.16em] text-slate-500">
            {label}
          </span>
        </div>
        <p className="text-kr text-sm leading-7 text-slate-700">{value}</p>
      </div>
    </div>
  );
}
