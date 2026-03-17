import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getWeeklyBundle, listWeeks } from "../services/api/weekly";
import {
  getWeekSelectionById,
  hydrateWeeklyQuizSubmissionDetail,
  normalizeWeeklyBundle,
} from "../services/adapters/weekly";
import type {
  WeeklyBundlePayload,
  WeeklyLearnerMemo,
  WeeklyQuizSubmissionDetailResponse,
  WeeklyQuizSubmissionResponse,
  WeeklySelection,
} from "../types/api";

interface WeeklyWorkspaceContextValue {
  weeks: WeeklySelection[];
  bundle: WeeklyBundlePayload | null;
  latestSubmission: WeeklyQuizSubmissionDetailResponse | null;
  learnerMemo: WeeklyLearnerMemo | null;
  loading: boolean;
  error: string | null;
  applyQuizSubmission: (submission: WeeklyQuizSubmissionResponse) => void;
  refetch: () => void;
}

const WeeklyWorkspaceContext = createContext<WeeklyWorkspaceContextValue | null>(null);

export function WeeklyWorkspaceProvider({
  weekId,
  children,
}: {
  weekId: string;
  children: React.ReactNode;
}) {
  const [weeks, setWeeks] = useState<WeeklySelection[]>([]);
  const [bundle, setBundle] = useState<WeeklyBundlePayload | null>(null);
  const [latestSubmission, setLatestSubmission] =
    useState<WeeklyQuizSubmissionDetailResponse | null>(null);
  const [learnerMemo, setLearnerMemo] = useState<WeeklyLearnerMemo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);

  useEffect(() => {
    const abortController = new AbortController();
    let active = true;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const [availableWeeks, weeklyBundleResponse] = await Promise.all([
          listWeeks(abortController.signal),
          getWeeklyBundle(weekId, abortController.signal),
        ]);

        if (!active) {
          return;
        }

        const week = getWeekSelectionById(availableWeeks, weekId);
        if (!week) {
          throw new Error(
            `The weekly API returned bundle data for week ${weekId}, but /weeks did not include matching weekly metadata.`,
          );
        }

        setWeeks(availableWeeks);
        setBundle(normalizeWeeklyBundle(week, weeklyBundleResponse));
        setLatestSubmission(null);
        setLearnerMemo(null);
      } catch (caughtError) {
        if (!active || abortController.signal.aborted) {
          return;
        }

        setBundle(null);
        setLatestSubmission(null);
        setLearnerMemo(null);
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "Unknown error while loading weekly data.",
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      active = false;
      abortController.abort();
    };
  }, [refreshCount, weekId]);

  function applyQuizSubmission(submission: WeeklyQuizSubmissionResponse) {
    if (!bundle) {
      return;
    }
    setLatestSubmission(hydrateWeeklyQuizSubmissionDetail(bundle.quiz, submission));
    setLearnerMemo(submission.learner_memo ?? null);
  }

  const contextValue = useMemo(
    () => ({
      weeks,
      bundle,
      latestSubmission,
      learnerMemo,
      loading,
      error,
      applyQuizSubmission,
      refetch: () => setRefreshCount((value) => value + 1),
    }),
    [bundle, error, latestSubmission, learnerMemo, loading, weeks],
  );

  return (
    <WeeklyWorkspaceContext.Provider value={contextValue}>
      {children}
    </WeeklyWorkspaceContext.Provider>
  );
}

export function useWeeklyWorkspace() {
  const contextValue = useContext(WeeklyWorkspaceContext);
  if (!contextValue) {
    throw new Error("useWeeklyWorkspace must be used inside WeeklyWorkspaceProvider");
  }
  return contextValue;
}
