import type {
  AnswerMap,
  QuestionProfile,
  TopicAxis,
  WeeklyBundleApiResponse,
  WeeklyBundlePayload,
  WeeklyGuide,
  WeeklyLearnerMemo,
  WeeklyQuizLearnerItem,
  WeeklyQuizLearnerSet,
  WeeklyQuizReviewResult,
  WeeklyQuizSubmissionDetailResponse,
  WeeklyQuizSubmissionRequest,
  WeeklyQuizSubmissionResponse,
  WeeklyQuizSubmissionResult,
  WeeklyQuestionTypeMetric,
  WeeklyReport,
  WeeklySelection,
} from "../../types/api";

const PROFILE_LABELS: Record<QuestionProfile, string> = {
  basic_eval_4: "기초 확인",
  review_5: "복습 확인",
  retest_5: "다시 확인",
};

export function formatWeekRange(dates: string[]) {
  if (!dates.length) {
    return "Weekly bundle";
  }
  if (dates.length === 1) {
    return dates[0];
  }
  return `${dates[0]} - ${dates[dates.length - 1]}`;
}

export function formatWeekLabel(week: WeeklySelection) {
  return `Week ${week.week}`;
}

export function getWeekSelectionById(weeks: WeeklySelection[], weekId: string) {
  return weeks.find((week) => week.week_id === weekId) ?? null;
}

export function normalizeWeeklyBundle(
  week: WeeklySelection,
  response: WeeklyBundleApiResponse,
): WeeklyBundlePayload {
  return {
    week,
    topics: response.topics,
    guide: response.guide,
    quiz: response.quiz_set,
    report: response.report,
  };
}

export function getWeeklyMismatchNotes(bundle: WeeklyBundlePayload) {
  const notes = [
    "The backend bundle response omits weekly selection metadata, so the frontend joins `/weeks` with `/weekly-bundle/{week_id}`.",
    "The current weekly report is a generation-coverage report, not a learner performance report.",
  ];

  const generatedGoalCount = bundle.quiz.items.filter(
    (item) => item.learning_goal_source !== "metadata",
  ).length;
  if (generatedGoalCount > 0) {
    notes.push(
      `${generatedGoalCount}/${bundle.quiz.items.length} quiz items currently expose generated learning goals instead of curriculum metadata.`,
    );
  }

  return notes;
}

function splitGuideSentences(text: string) {
  return text
    .trim()
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

export function getGuideLeadText(text: string, maxSentences = 2) {
  const sentences = splitGuideSentences(text);
  if (!sentences.length) {
    return "이번 주 학습 흐름을 한 화면에서 정리해 보세요.";
  }
  return sentences.slice(0, maxSentences).join(" ");
}

export function getTopicAxisPreviewLabels(topicAxes: TopicAxis[], limit = 2) {
  return topicAxes.slice(0, limit).map((axis) => axis.label);
}

export function getHubOverviewCopy(guide: WeeklyGuide) {
  return {
    title: "이번 주 학습 허브",
    description: getGuideLeadText(guide.learning_paragraph, 2),
  };
}

export function getQuizOverviewCopy(guide: WeeklyGuide, totalQuestions: number) {
  const labels = getTopicAxisPreviewLabels(guide.topic_axes, 2);
  const focusText = labels.length ? `${labels.join(" · ")}를 중심으로 ` : "";

  return {
    title: "핵심 개념 확인 퀴즈",
    description: `${focusText}${totalQuestions}문항을 순서대로 풀고 제출한 뒤, 결과와 해설을 확인합니다.`,
  };
}

export function getReportOverviewCopy(guide: WeeklyGuide) {
  const labels = getTopicAxisPreviewLabels(guide.topic_axes, 2);
  const focusText = labels.length ? `${labels.join(" · ")}를 중심으로 ` : "";

  return {
    title: "주간 학습 리포트",
    description: `${focusText}이번 주 문항 구성과 주제 분포를 한눈에 정리했습니다.`,
  };
}

export function getProfileLabel(profile: string) {
  return PROFILE_LABELS[profile as QuestionProfile] ?? profile;
}

export function getProfileAccentClass(profile: string) {
  if (profile === "basic_eval_4") {
    return "bg-sky-100 text-sky-700 border-sky-200";
  }
  if (profile === "review_5") {
    return "bg-amber-100 text-amber-700 border-amber-200";
  }
  return "bg-orange-100 text-orange-700 border-orange-200";
}

export function getTopicQuestionCount(items: WeeklyQuizLearnerItem[], label: string) {
  return items.filter((item) => item.topic_axis_label === label).length;
}

export function findTopicAxis(topicAxes: TopicAxis[], label: string) {
  return topicAxes.find((axis) => axis.label === label);
}

export function getRecommendedReviewItems(
  guide: WeeklyGuide,
  report: WeeklyReport,
  learnerMemo?: WeeklyLearnerMemo | null,
  submission?: WeeklyQuizSubmissionDetailResponse | null,
  limit = 3,
) {
  const wrongResults = getWrongReviewResults(submission ?? null);
  if (learnerMemo?.status === "ready" && wrongResults.length > 0) {
    const wrongCountByDate = new Map<string, number>();
    const firstWrongByDate = new Map<string, WeeklyQuizReviewResult>();

    for (const result of wrongResults) {
      wrongCountByDate.set(result.source_date, (wrongCountByDate.get(result.source_date) ?? 0) + 1);
      if (!firstWrongByDate.has(result.source_date)) {
        firstWrongByDate.set(result.source_date, result);
      }
    }

    const sortedDates = [...wrongCountByDate.keys()].sort((left, right) =>
      left.localeCompare(right),
    );

    return sortedDates.slice(0, limit).map((sourceDate) => {
      const representativeWrong = firstWrongByDate.get(sourceDate);
      return {
        title:
          getReviewKnowledgeStatement(representativeWrong) ??
          `${sourceDate} 강의에서 틀린 개념을 다시 확인하세요.`,
        meta: representativeWrong?.topic_axis_label ?? "이번 주 핵심 주제",
      };
    });
  }

  const lowCoverageLabels = [...report.topic_coverage]
    .sort((left, right) => left.question_count - right.question_count)
    .map((coverage) => coverage.topic_axis_label);

  return guide.review_points.slice(0, limit).map((reviewPoint, index) => {
    const topicLabel = lowCoverageLabels[index] ?? guide.topic_axes[index]?.label ?? "Weekly review";
    return {
      title: reviewPoint,
      meta: topicLabel,
    };
  });
}

function getReviewKnowledgeStatement(result?: WeeklyQuizReviewResult) {
  if (!result) {
    return null;
  }

  const answerText = result.answer_text.trim();
  if (answerText) {
    return answerText;
  }

  const explanationSentence = result.explanation
    .trim()
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .find(Boolean);

  return explanationSentence ?? null;
}

export function getQuestionTypeShare(
  metrics: WeeklyQuestionTypeMetric[],
  totalQuestions: number,
) {
  return metrics.map((metric) => ({
    ...metric,
    share: totalQuestions > 0 ? Math.round((metric.question_count / totalQuestions) * 100) : 0,
    label: getProfileLabel(metric.question_profile),
  }));
}

export function getTopicCoverageShare(report: WeeklyReport, totalQuestions: number) {
  return report.topic_coverage.map((coverage) => ({
    ...coverage,
    share: totalQuestions > 0 ? Math.round((coverage.question_count / totalQuestions) * 100) : 0,
  }));
}

export function getWeeklyFallbackNote(guide: WeeklyGuide, report: WeeklyReport) {
  return (
    report.notes[0] ??
    guide.review_points[0] ??
    "이번 주 핵심 개념을 순서대로 다시 점검해 보세요."
  );
}

export function getLearnerMemoReviewPoints(
  learnerMemo: WeeklyLearnerMemo | null,
  guide: WeeklyGuide,
  limit = 3,
) {
  const memoPoints = learnerMemo?.recommended_review_points.filter(Boolean) ?? [];
  if (memoPoints.length) {
    return memoPoints.slice(0, limit);
  }
  return guide.review_points.slice(0, limit);
}

export function hydrateWeeklyQuizSubmissionDetail(
  quiz: WeeklyQuizLearnerSet,
  submission: WeeklyQuizSubmissionResponse,
): WeeklyQuizSubmissionDetailResponse {
  const itemById = new Map(quiz.items.map((item) => [item.item_id, item]));
  const results: WeeklyQuizReviewResult[] = [];
  for (const result of submission.results) {
    const item = itemById.get(result.item_id);
    if (!item) {
      continue;
    }
    results.push({
      item_id: item.item_id,
      question: item.question,
      options: item.options,
      selected_option_index: result.selected_option_index,
      correct_option_index: result.correct_option_index,
      answer_text: result.answer_text,
      explanation: result.explanation,
      is_correct: result.is_correct,
      topic_axis_label: item.topic_axis_label,
      source_corpus_id: item.source_corpus_id,
      source_date: item.source_date,
      learning_goal: item.learning_goal,
      learning_goal_source: item.learning_goal_source,
      retrieved_chunk_ids: item.retrieved_chunk_ids,
      evidence_chunk_ids: item.evidence_chunk_ids,
    });
  }

  return {
    attempt_id: submission.attempt_id,
    week_id: submission.week_id,
    total_questions: submission.total_questions,
    correct_count: submission.correct_count,
    score: submission.score,
    submitted_at: submission.submitted_at,
    results,
  };
}

export function getLearningGoalSourceSummary(report: WeeklyReport) {
  const distribution = report.learning_goal_source_distribution ?? {};
  const entries = Object.entries(distribution);
  if (!entries.length) {
    return "Learning goal source data unavailable";
  }
  return entries.map(([source, count]) => `${source}: ${count}`).join(" / ");
}

export function getStrictFieldReadyCount(items: WeeklyQuizLearnerItem[]) {
  return items.filter((item) => {
    return Boolean(
      item.topic_axis_label &&
        item.source_corpus_id &&
        item.source_date &&
        item.retrieved_chunk_ids.length &&
        item.evidence_chunk_ids.length,
    );
  }).length;
}

export function createAnswerMap(items: WeeklyQuizLearnerItem[]): AnswerMap {
  return items.reduce<AnswerMap>((answerMap, item) => {
    if (item.item_id) {
      answerMap[item.item_id] = null;
    }
    return answerMap;
  }, {});
}

export function isQuizSubmitReady(items: WeeklyQuizLearnerItem[]) {
  return items.length > 0 && items.every((item) => Boolean(item.item_id));
}

export function getAnsweredCount(answerMap: AnswerMap) {
  return Object.values(answerMap).filter((value) => value !== null).length;
}

export function getUnansweredQuestionNumbers(
  items: WeeklyQuizLearnerItem[],
  answerMap: AnswerMap,
) {
  return items.reduce<number[]>((numbers, item, index) => {
    if (answerMap[item.item_id] === null || answerMap[item.item_id] === undefined) {
      numbers.push(index + 1);
    }
    return numbers;
  }, []);
}

export function buildWeeklyQuizSubmissionRequest(
  answerMap: AnswerMap,
): WeeklyQuizSubmissionRequest {
  return {
    answers: Object.entries(answerMap)
      .filter(([, selectedOptionIndex]) => selectedOptionIndex !== null)
      .map(([itemId, selectedOptionIndex]) => ({
        item_id: itemId,
        selected_option_index: selectedOptionIndex as number,
      })),
  };
}

export function getSubmissionResultMap(
  submission: WeeklyQuizSubmissionResponse | null,
) {
  return (submission?.results ?? []).reduce<Record<string, WeeklyQuizSubmissionResult>>(
    (resultMap, result) => {
      resultMap[result.item_id] = result;
      return resultMap;
    },
    {},
  );
}

export function getWrongReviewResults(
  submission: WeeklyQuizSubmissionDetailResponse | null,
) {
  return (submission?.results ?? []).filter((result) => !result.is_correct);
}

export function getReviewPagination(totalItems: number, pageSize: number, currentPage: number) {
  const totalPages = totalItems > 0 ? Math.ceil(totalItems / pageSize) : 0;
  const safePage = totalPages > 0 ? Math.min(currentPage, totalPages - 1) : 0;
  const start = safePage * pageSize;
  const end = start + pageSize;

  return {
    totalPages,
    safePage,
    start,
    end,
  };
}

export function getPagedReviewResults(
  items: WeeklyQuizReviewResult[],
  currentPage: number,
  pageSize: number,
) {
  const { start, end } = getReviewPagination(items.length, pageSize, currentPage);
  return items.slice(start, end);
}

export function getSelectedAnswerText(result: WeeklyQuizReviewResult) {
  if (result.selected_option_index === null) {
    return "미응답";
  }
  return result.options[result.selected_option_index] ?? "선택 정보 없음";
}

export function getSearchFilteredTopicAxes(topicAxes: TopicAxis[], query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return topicAxes;
  }

  return topicAxes.filter((axis) => {
    return (
      axis.label.toLowerCase().includes(normalizedQuery) ||
      axis.supporting_terms.some((term) => term.toLowerCase().includes(normalizedQuery))
    );
  });
}

export function getSearchFilteredReviewPoints(reviewPoints: string[], query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return reviewPoints;
  }

  return reviewPoints.filter((reviewPoint) =>
    reviewPoint.toLowerCase().includes(normalizedQuery),
  );
}

export function getQuestionPrompt(item: WeeklyQuizLearnerItem, index: number, total: number) {
  return {
    eyebrow: `${index + 1} / ${total}`,
    title: item.question,
    meta: getProfileLabel(item.question_profile),
  };
}
