import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { QuestionReviewPanel } from "../components/report/QuestionReviewPanel";
import { ProfileDistributionPanel } from "../components/report/ProfileDistributionPanel";
import { ReportMetricCards } from "../components/report/ReportMetricCards";
import { TopicCoveragePanel } from "../components/report/TopicCoveragePanel";
import { LearnerMemoCard } from "../components/weekly/LearnerMemoCard";
import { WeekTabs } from "../components/weekly/WeekTabs";
import { useWeeklyReportResponse } from "../hooks/useWeeklyReportResponse";
import { ApiError } from "../services/api/client";
import { getLatestWeeklyQuizSubmission } from "../services/api/weekly";
import {
  getLearnerMemoReviewPoints,
  getPagedReviewResults,
  getReportOverviewCopy,
  getReviewPagination,
  getTopicAxisPreviewLabels,
  getWeeklyFallbackNote,
  getWrongReviewResults,
} from "../services/adapters/weekly";
import { useWeeklyWorkspace } from "../providers/weekly-workspace";
import type { WeeklyQuizSubmissionDetailResponse } from "../types/api";

const REVIEW_PAGE_SIZE = 2;

export function WeekReportPage() {
  const { bundle, latestSubmission: cachedLatestSubmission, learnerMemo: cachedLearnerMemo } =
    useWeeklyWorkspace();
  const weekId = bundle?.week.week_id ?? null;
  const {
    reportResponse,
    loading: memoLoading,
    error: memoError,
    retry: retryMemo,
  } = useWeeklyReportResponse(weekId);
  const [latestSubmission, setLatestSubmission] =
    useState<WeeklyQuizSubmissionDetailResponse | null>(null);
  const [hasSubmission, setHasSubmission] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [reviewRefreshCount, setReviewRefreshCount] = useState(0);

  useEffect(() => {
    if (!weekId) {
      return;
    }
    const targetWeekId = weekId;

    const abortController = new AbortController();
    let active = true;

    async function loadLatestSubmission() {
      setReviewLoading(true);
      setReviewError(null);

      try {
        const response = await getLatestWeeklyQuizSubmission(
          targetWeekId,
          abortController.signal,
        );
        if (!active) {
          return;
        }
        setLatestSubmission(response);
        setHasSubmission(true);
      } catch (caughtError) {
        if (!active || abortController.signal.aborted) {
          return;
        }

        setLatestSubmission(null);
        if (caughtError instanceof ApiError && caughtError.status === 404) {
          setHasSubmission(false);
          setReviewError(null);
        } else {
          setHasSubmission(false);
          setReviewError(
            caughtError instanceof Error
              ? caughtError.message
              : "오답 리뷰를 불러오는 중 알 수 없는 오류가 발생했습니다.",
          );
        }
      } finally {
        if (active) {
          setReviewLoading(false);
        }
      }
    }

    void loadLatestSubmission();

    return () => {
      active = false;
      abortController.abort();
    };
  }, [reviewRefreshCount, weekId]);

  useEffect(() => {
    setCurrentPage(0);
  }, [bundle?.week.week_id, latestSubmission?.attempt_id]);

  if (!bundle) {
    return null;
  }
  const reportCopy = getReportOverviewCopy(bundle.guide);
  const topicLabels = getTopicAxisPreviewLabels(bundle.guide.topic_axes, 2);
  const fallbackNote = getWeeklyFallbackNote(bundle.guide, bundle.report);
  const effectiveLearnerMemo = cachedLearnerMemo ?? reportResponse?.learner_memo ?? null;
  const effectiveLatestSubmission = cachedLatestSubmission ?? latestSubmission;
  const memoReviewPoints = getLearnerMemoReviewPoints(
    effectiveLearnerMemo,
    bundle.guide,
    3,
  );
  const wrongItems = useMemo(
    () => getWrongReviewResults(effectiveLatestSubmission),
    [effectiveLatestSubmission],
  );
  const { safePage, totalPages } = useMemo(
    () => getReviewPagination(wrongItems.length, REVIEW_PAGE_SIZE, currentPage),
    [currentPage, wrongItems.length],
  );
  const pagedWrongItems = useMemo(
    () => getPagedReviewResults(wrongItems, safePage, REVIEW_PAGE_SIZE),
    [safePage, wrongItems],
  );

  return (
    <div className="min-h-screen bg-[#f8f7f5] px-4 py-4 text-slate-900 md:px-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="rounded-[32px] border border-white/60 bg-white/80 px-6 py-5 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
                주간 리포트
              </p>
              <h1 className="text-kr mt-2 max-w-3xl text-[clamp(2rem,4vw,3.4rem)] font-black leading-[1.25] tracking-tight">
                {reportCopy.title}
              </h1>
              <p className="text-kr mt-3 max-w-3xl text-sm leading-7 text-slate-500">
                {reportCopy.description}
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

            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-orange-200 hover:text-orange-600"
                to={`/weeks/${bundle.week.week_id}/hub`}
              >
                허브 보기
              </Link>
              <Link
                className="rounded-full bg-orange-500 px-5 py-3 text-sm font-bold text-white transition hover:bg-orange-600"
                to={`/weeks/${bundle.week.week_id}/quiz`}
              >
                퀴즈 보기
              </Link>
            </div>
          </div>
          <div className="mt-5">
            <WeekTabs weekId={bundle.week.week_id} />
          </div>
        </header>

        <LearnerMemoCard
          error={cachedLearnerMemo ? null : memoError}
          fallbackNote={fallbackNote}
          learnerMemo={effectiveLearnerMemo}
          loading={cachedLearnerMemo ? false : memoLoading}
          onRetry={retryMemo}
          reviewPoints={memoReviewPoints}
          weekId={bundle.week.week_id}
        />

        <ReportMetricCards quiz={bundle.quiz} report={bundle.report} />

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <ProfileDistributionPanel quiz={bundle.quiz} report={bundle.report} />
          <TopicCoveragePanel
            guide={bundle.guide}
            learnerMemo={effectiveLearnerMemo}
            quiz={bundle.quiz}
            report={bundle.report}
            submission={effectiveLatestSubmission}
          />
        </div>

        <QuestionReviewPanel
          currentPage={safePage}
          error={cachedLatestSubmission ? null : reviewError}
          hasSubmission={cachedLatestSubmission !== null || hasSubmission}
          items={pagedWrongItems}
          loading={cachedLatestSubmission ? false : reviewLoading}
          onNextPage={() =>
            setCurrentPage((value) => Math.min(Math.max(totalPages - 1, 0), value + 1))
          }
          onPreviousPage={() => setCurrentPage((value) => Math.max(0, value - 1))}
          onRetry={() => setReviewRefreshCount((value) => value + 1)}
          totalPages={totalPages}
          weekId={bundle.week.week_id}
          wrongItemCount={wrongItems.length}
        />
      </div>
    </div>
  );
}
