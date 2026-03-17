import type {
  WeeklyQuizSubmissionRequest,
  WeeklyQuizSubmissionDetailResponse,
  WeeklyQuizSubmissionResponse,
  WeeklyBundleApiResponse,
  WeeklyGuide,
  WeeklyQuizLearnerSet,
  WeeklyReportResponse,
  WeeklySelection,
  WeeklyTopicSet,
} from "../../types/api";
import { fetchJson } from "./client";

export function listWeeks(signal?: AbortSignal) {
  return fetchJson<WeeklySelection[]>("/weeks", { signal });
}

export function getWeeklyTopics(weekId: string, signal?: AbortSignal) {
  return fetchJson<WeeklyTopicSet>(`/weekly-topics/${weekId}`, { signal });
}

export function getWeeklyGuide(weekId: string, signal?: AbortSignal) {
  return fetchJson<WeeklyGuide>(`/weekly-guide/${weekId}`, { signal });
}

export function getWeeklyQuiz(weekId: string, signal?: AbortSignal) {
  return fetchJson<WeeklyQuizLearnerSet>(`/weekly-quiz/${weekId}`, { signal });
}

export function getWeeklyReport(weekId: string, signal?: AbortSignal) {
  return fetchJson<WeeklyReportResponse>(`/weekly-report/${weekId}`, { signal });
}

export function getWeeklyBundle(weekId: string, signal?: AbortSignal) {
  return fetchJson<WeeklyBundleApiResponse>(`/weekly-bundle/${weekId}`, { signal });
}

export function submitWeeklyQuiz(
  weekId: string,
  payload: WeeklyQuizSubmissionRequest,
  signal?: AbortSignal,
) {
  return fetchJson<WeeklyQuizSubmissionResponse>(`/weekly-quiz/${weekId}/submit`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
}

export function getLatestWeeklyQuizSubmission(weekId: string, signal?: AbortSignal) {
  return fetchJson<WeeklyQuizSubmissionDetailResponse>(
    `/weekly-quiz/${weekId}/latest-submission`,
    { signal },
  );
}
