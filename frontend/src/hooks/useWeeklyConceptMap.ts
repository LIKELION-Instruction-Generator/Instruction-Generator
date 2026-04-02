import { useEffect, useState } from "react";
import { getWeeklyConceptMap } from "../services/api/weekly";
import type { WeeklyConceptMapResponse } from "../types/api";

export function useWeeklyConceptMap(weekId: string | null) {
  const [data, setData] = useState<WeeklyConceptMapResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);

  useEffect(() => {
    if (!weekId) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }
    const targetWeekId = weekId;

    const abortController = new AbortController();
    let active = true;

    async function loadConceptMap() {
      setLoading(true);
      setError(null);

      try {
        const response = await getWeeklyConceptMap(targetWeekId, abortController.signal);
        if (!active) {
          return;
        }
        setData(response);
      } catch (caughtError) {
        if (!active || abortController.signal.aborted) {
          return;
        }
        setData(null);
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : "개념 맵을 불러오는 중 알 수 없는 오류가 발생했습니다.",
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadConceptMap();

    return () => {
      active = false;
      abortController.abort();
    };
  }, [refreshCount, weekId]);

  return {
    data,
    loading,
    error,
    retry: () => setRefreshCount((value) => value + 1),
  };
}
