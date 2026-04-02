import { useDeferredValue, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ConceptMapPanel } from "../components/weekly/ConceptMapPanel";
import { WeekActionRail } from "../components/weekly/WeekActionRail";
import { WeekSelector } from "../components/weekly/WeekSelector";
import { WeekSummaryCard } from "../components/weekly/WeekSummaryCard";
import { WeekTabs } from "../components/weekly/WeekTabs";
import { useWeeklyReportResponse } from "../hooks/useWeeklyReportResponse";
import {
  getHubOverviewCopy,
  getSearchFilteredTopicAxes,
  getTopicAxisPreviewLabels,
} from "../services/adapters/weekly";
import { useWeeklyWorkspace } from "../providers/weekly-workspace";

export function WeekHubPage() {
  const navigate = useNavigate();
  const { bundle, learnerMemo, weeks } = useWeeklyWorkspace();
  const [search, setSearch] = useState("");
  const [sidebarMinHeight, setSidebarMinHeight] = useState<number | null>(null);
  const deferredSearch = useDeferredValue(search);
  const rightRailRef = useRef<HTMLDivElement | null>(null);
  const {
    reportResponse,
    loading: memoLoading,
    error: memoError,
    retry: retryMemo,
  } = useWeeklyReportResponse(bundle?.week.week_id ?? null);

  useEffect(() => {
    if (!bundle) {
      return;
    }
    const targetNode = rightRailRef.current;
    if (!targetNode || typeof ResizeObserver === "undefined") {
      return;
    }

    const syncHeight = () => {
      if (typeof window !== "undefined" && !window.matchMedia("(min-width: 1280px)").matches) {
        setSidebarMinHeight(null);
        return;
      }
      setSidebarMinHeight(Math.ceil(targetNode.getBoundingClientRect().height));
    };

    syncHeight();
    const observer = new ResizeObserver(() => {
      syncHeight();
    });
    observer.observe(targetNode);
    window.addEventListener("resize", syncHeight);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", syncHeight);
    };
  }, [bundle?.week.week_id]);

  if (!bundle) {
    return null;
  }

  const filteredTopicAxes = getSearchFilteredTopicAxes(
    bundle.topics.topic_axes,
    deferredSearch,
  );
  const effectiveLearnerMemo = learnerMemo ?? reportResponse?.learner_memo ?? null;
  const hubCopy = getHubOverviewCopy(bundle.guide);
  const topicLabels = getTopicAxisPreviewLabels(bundle.guide.topic_axes, 2);

  return (
    <div className="min-h-screen bg-[#f8f7f5] text-slate-900">
      <div className="mx-auto flex max-w-[1600px] gap-6 px-4 py-4 lg:px-6">
        <aside
          className="sticky top-4 hidden h-fit w-72 shrink-0 rounded-[32px] border border-white/50 bg-white/90 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.08)] lg:flex lg:flex-col"
          style={sidebarMinHeight ? { minHeight: `${sidebarMinHeight}px` } : undefined}
        >
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-orange-500 p-3 text-sm font-black text-white">STT</div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
                Weekly
              </p>
              <h1 className="text-xl font-black tracking-tight">학습 허브</h1>
            </div>
          </div>

          <div className="mt-8 space-y-2">
            <NavChip active label="학습 허브" to={`/weeks/${bundle.week.week_id}/hub`} />
            <NavChip label="주간 퀴즈" to={`/weeks/${bundle.week.week_id}/quiz`} />
            <NavChip label="학습 리포트" to={`/weeks/${bundle.week.week_id}/report`} />
          </div>

          <div className="mt-8">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              주차 선택
            </p>
            <div className="mt-3 space-y-2">
              {weeks.map((w) => {
                const isActive = w.week_id === bundle.week.week_id;
                return (
                  <button
                    className={`w-full rounded-[20px] border px-4 py-3 text-left text-sm font-semibold transition ${
                      isActive
                        ? "border-orange-200 bg-orange-50 text-orange-700"
                        : "border-slate-100 text-slate-500 hover:bg-slate-50 hover:text-orange-600"
                    }`}
                    key={w.week_id}
                    onClick={() => navigate(`/weeks/${w.week_id}/hub`)}
                    type="button"
                  >
                    {w.week}주차
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          <div className="rounded-[32px] border border-white/50 bg-white/70 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.06)] backdrop-blur">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
              <div className="min-w-0 max-w-4xl">
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
                  Week {bundle.week.week}
                </p>
                <h1 className="text-kr mt-2 text-[clamp(2rem,4vw,3.5rem)] font-black leading-[1.2] tracking-tight text-slate-900">
                  {hubCopy.title}
                </h1>
                <p className="text-kr mt-3 max-w-3xl text-sm leading-7 text-slate-500">
                  {hubCopy.description}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  {topicLabels.map((label) => (
                    <span
                      className="rounded-full border border-orange-200 bg-orange-50 px-3 py-2 text-xs font-semibold text-orange-700"
                      key={label}
                    >
                      {label}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row">
                <input
                  className="h-12 rounded-full border border-slate-200 bg-white px-5 text-sm outline-none transition focus:border-orange-300"
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="주제, 키워드, 복습 포인트 검색"
                  value={search}
                />
                <Link
                  className="inline-flex h-12 items-center justify-center whitespace-nowrap rounded-full bg-orange-500 px-5 text-sm font-bold text-white transition hover:bg-orange-600"
                  to={`/weeks/${bundle.week.week_id}/quiz`}
                >
                  퀴즈 검색
                </Link>
              </div>
            </div>

            <div className="mt-5 flex flex-col gap-3">
              <WeekSelector />
              <WeekTabs weekId={bundle.week.week_id} />
            </div>
          </div>

          <div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="space-y-6">
              <WeekSummaryCard
                guide={bundle.guide}
                minHeight={sidebarMinHeight}
                quiz={bundle.quiz}
                topicAxes={filteredTopicAxes}
                week={bundle.week}
              />
            </div>

            <div className="xl:sticky xl:top-4" ref={rightRailRef}>
              <WeekActionRail
                bundle={bundle}
                learnerMemo={effectiveLearnerMemo}
                memoError={learnerMemo ? null : memoError}
                memoLoading={learnerMemo ? false : memoLoading}
                onRetryMemo={retryMemo}
                quiz={bundle.quiz}
                report={bundle.report}
                week={bundle.week}
              />
            </div>
          </div>

          <div className="mt-6">
            <ConceptMapPanel weekId={bundle.week.week_id} />
          </div>
        </main>
      </div>
    </div>
  );
}

function NavChip({
  active = false,
  label,
  to,
}: {
  active?: boolean;
  label: string;
  to: string;
}) {
  return (
    <Link
      className={`block rounded-[20px] px-4 py-3 text-sm font-semibold transition ${
        active
          ? "bg-orange-50 text-orange-700"
          : "text-slate-500 hover:bg-slate-50 hover:text-orange-600"
      }`}
      to={to}
    >
      {label}
    </Link>
  );
}
