import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { QuestionProgress } from "../components/quiz/QuestionProgress";
import { QuizQuestionCard } from "../components/quiz/QuizQuestionCard";
import { WeekTabs } from "../components/weekly/WeekTabs";
import { ApiError } from "../services/api/client";
import { submitWeeklyQuiz } from "../services/api/weekly";
import {
  buildWeeklyQuizSubmissionRequest,
  createAnswerMap,
  getAnsweredCount,
  getUnansweredQuestionNumbers,
  getQuizOverviewCopy,
  getSubmissionResultMap,
  getTopicAxisPreviewLabels,
  isQuizSubmitReady,
} from "../services/adapters/weekly";
import { useWeeklyWorkspace } from "../providers/weekly-workspace";
import type { AnswerMap, WeeklyQuizSubmissionResponse } from "../types/api";

export function WeekQuizPage() {
  const { applyQuizSubmission, bundle } = useWeeklyWorkspace();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [submission, setSubmission] = useState<WeeklyQuizSubmissionResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [localValidationMessage, setLocalValidationMessage] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const quizItems = bundle?.quiz.items ?? [];

  const interactiveReady = isQuizSubmitReady(quizItems);

  useEffect(() => {
    if (!bundle) {
      return;
    }
    setAnswers(createAnswerMap(bundle.quiz.items));
    setSubmission(null);
    setSubmitting(false);
    setLocalValidationMessage(null);
    setSubmitError(null);
    setCurrentIndex(0);
  }, [bundle?.quiz.items, bundle?.week.week_id]);

  if (!bundle) {
    return null;
  }

  const currentItem = bundle.quiz.items[currentIndex];
  const lastQuestion = currentIndex === bundle.quiz.items.length - 1;
  const quizCopy = getQuizOverviewCopy(bundle.guide, bundle.quiz.items.length);
  const topicLabels = getTopicAxisPreviewLabels(bundle.guide.topic_axes, 2);
  const answeredCount = getAnsweredCount(answers);
  const unansweredQuestionNumbers = getUnansweredQuestionNumbers(bundle.quiz.items, answers);
  const allQuestionsAnswered = unansweredQuestionNumbers.length === 0;
  const unansweredMessage = unansweredQuestionNumbers.length
    ? `아직 답하지 않은 문항: ${unansweredQuestionNumbers.map((number) => `${number}번`).join(", ")}`
    : null;
  const submissionResultMap = useMemo(
    () => getSubmissionResultMap(submission),
    [submission],
  );
  const currentResult = currentItem ? submissionResultMap[currentItem.item_id] ?? null : null;

  function handleSelectAnswer(itemId: string, optionIndex: number) {
    if (submission) {
      return;
    }
    setAnswers((currentAnswers) => ({
      ...currentAnswers,
      [itemId]: optionIndex,
    }));
    setLocalValidationMessage(null);
    setSubmitError(null);
  }

  async function handleSubmit() {
    if (!bundle || !interactiveReady || submitting || submission) {
      return;
    }

    if (!allQuestionsAnswered) {
      setLocalValidationMessage(unansweredMessage);
      return;
    }

    setSubmitting(true);
    setLocalValidationMessage(null);
    setSubmitError(null);

    try {
      const response = await submitWeeklyQuiz(
        bundle.week.week_id,
        buildWeeklyQuizSubmissionRequest(answers),
      );
      setSubmission(response);
      applyQuizSubmission(response);
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 422) {
        setSubmitError(`제출 조건을 다시 확인해 주세요. ${caughtError.detail}`);
      } else {
        setSubmitError(
          caughtError instanceof Error
            ? caughtError.message
            : "제출 중 알 수 없는 오류가 발생했습니다.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f8f7f5] px-4 py-4 text-slate-900 md:px-6">
      <div className="mx-auto max-w-5xl">
        <header className="rounded-[32px] border border-white/60 bg-white/80 px-6 py-5 shadow-[0_24px_80px_rgba(15,23,42,0.08)] backdrop-blur">
          <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-500">
                주간 퀴즈
              </p>
              <h1 className="text-kr mt-2 max-w-3xl text-[clamp(1.9rem,4vw,3rem)] font-black leading-[1.25] tracking-tight">
                {quizCopy.title}
              </h1>
              <p className="text-kr mt-3 max-w-3xl text-sm leading-7 text-slate-500">
                {quizCopy.description}
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
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-orange-50 px-4 py-2 text-xs font-semibold text-orange-600">
                {bundle.quiz.items.length}문항
              </span>
              <span className="rounded-full bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-500">
                {submission ? "제출 완료" : `${answeredCount}/${bundle.quiz.items.length} 응답`}
              </span>
            </div>
          </div>
          <div className="mt-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <WeekTabs weekId={bundle.week.week_id} />
            <Link
              className="text-sm font-semibold text-slate-500 transition hover:text-orange-600"
              to={`/weeks/${bundle.week.week_id}/hub`}
            >
              허브로 돌아가기
            </Link>
          </div>
        </header>

        <div className="mt-6 space-y-6">
          <section className="rounded-[28px] border border-orange-200 bg-orange-50 px-6 py-5 shadow-[0_20px_60px_rgba(249,115,22,0.12)]">
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-orange-600">
              {submission ? "제출 결과" : "이번 주 퀴즈 안내"}
            </p>
            {submission ? (
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <SummaryTile label="점수" value={`${submission.score}점`} />
                <SummaryTile
                  label="정답 수"
                  value={`${submission.correct_count}/${submission.total_questions}`}
                />
                <SummaryTile label="응답 수" value={`${answeredCount}문항`} />
              </div>
            ) : (
              <div className="mt-3 space-y-3">
                <p className="text-kr text-sm leading-6 text-slate-700">
                  모든 문항에 답한 뒤 제출하면 서버 채점 결과가 열리고, 그 이후에 정답과 해설을 확인할 수 있습니다.
                </p>
                {unansweredMessage ? (
                  <p className="text-kr rounded-[18px] border border-amber-200 bg-white/80 px-4 py-3 text-sm leading-6 text-amber-700">
                    {unansweredMessage}
                  </p>
                ) : (
                  <p className="rounded-[18px] border border-emerald-200 bg-white/80 px-4 py-3 text-sm font-semibold text-emerald-700">
                    전 문항 응답 완료. 제출할 수 있습니다.
                  </p>
                )}
              </div>
            )}
            {!interactiveReady ? (
              <p className="text-kr mt-4 text-sm leading-6 text-red-600">
                현재 퀴즈 계약이 제출 준비 상태가 아니어서 답안을 전송할 수 없습니다.
              </p>
            ) : null}
            {localValidationMessage ? (
              <p className="text-kr mt-4 text-sm leading-6 text-amber-700">
                {localValidationMessage}
              </p>
            ) : null}
            {submitError ? (
              <p className="text-kr mt-4 text-sm leading-6 text-red-600">{submitError}</p>
            ) : null}
          </section>

          <QuestionProgress
            answeredCount={answeredCount}
            contractLabel={`회차당 ${bundle.quiz.min_questions_per_corpus}문항`}
            correctCount={submission?.correct_count}
            currentIndex={currentIndex}
            score={submission?.score}
            submitted={Boolean(submission)}
            total={bundle.quiz.items.length}
            unansweredCount={unansweredQuestionNumbers.length}
          />

          {currentItem ? (
            <QuizQuestionCard
              item={currentItem}
              onSelectOption={(optionIndex) => handleSelectAnswer(currentItem.item_id, optionIndex)}
              questionIndex={currentIndex}
              selectedOptionIndex={answers[currentItem.item_id] ?? null}
              submissionResult={currentResult}
              submitted={Boolean(submission)}
              totalQuestions={bundle.quiz.items.length}
            />
          ) : null}

          <footer className="flex flex-col gap-4 rounded-[28px] border border-slate-100 bg-white px-6 py-5 shadow-[0_24px_80px_rgba(15,23,42,0.08)] md:flex-row md:items-center md:justify-between">
            <button
              className="rounded-full border border-slate-200 px-5 py-3 text-sm font-semibold text-slate-600 transition hover:border-orange-200 hover:text-orange-600 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={currentIndex === 0}
              onClick={() => setCurrentIndex((value) => Math.max(0, value - 1))}
              type="button"
            >
              이전 문제
            </button>

            <div className="flex flex-col gap-3 md:items-end">
              {unansweredMessage && !submission ? (
                <p className="text-kr text-sm leading-6 text-amber-700">{unansweredMessage}</p>
              ) : null}
              <Link
                className="rounded-full border border-slate-200 px-5 py-3 text-sm font-semibold text-slate-600 transition hover:border-orange-200 hover:text-orange-600"
                to={`/weeks/${bundle.week.week_id}/report`}
              >
                리포트 보기
              </Link>
              <div className="flex flex-wrap gap-3">
                <button
                  className="rounded-full border border-orange-200 bg-orange-50 px-5 py-3 text-sm font-bold text-orange-700 transition hover:border-orange-300 hover:bg-orange-100 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={
                    !interactiveReady ||
                    submitting ||
                    submission !== null ||
                    !allQuestionsAnswered
                  }
                  onClick={() => void handleSubmit()}
                  type="button"
                >
                  {submission ? "제출 완료" : submitting ? "제출 중..." : "제출하기"}
                </button>

                <button
                  className="rounded-full bg-orange-500 px-5 py-3 text-sm font-bold text-white transition hover:bg-orange-600 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={lastQuestion}
                  onClick={() =>
                    setCurrentIndex((value) =>
                      Math.min(bundle.quiz.items.length - 1, value + 1),
                    )
                  }
                  type="button"
                >
                  {lastQuestion ? "마지막 문제" : "다음 문제"}
                </button>
              </div>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] border border-white/60 bg-white/85 px-4 py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-black tracking-tight text-slate-900">{value}</p>
    </div>
  );
}
