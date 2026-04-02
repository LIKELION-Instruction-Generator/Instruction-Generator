import {
  getProfileAccentClass,
  getProfileLabel,
  getQuestionPrompt,
} from "../../services/adapters/weekly";
import type {
  WeeklyQuizLearnerItem,
  WeeklyQuizSubmissionResult,
} from "../../types/api";

export function QuizQuestionCard({
  item,
  questionIndex,
  totalQuestions,
  selectedAnswer,
  submitted = false,
  submissionResult,
  onAnswer,
}: {
  item: WeeklyQuizLearnerItem;
  questionIndex: number;
  totalQuestions: number;
  selectedAnswer: number | string | null;
  submitted?: boolean;
  submissionResult?: WeeklyQuizSubmissionResult | null;
  onAnswer: (answer: number | string) => void;
}) {
  const prompt = getQuestionPrompt(item, questionIndex, totalQuestions);
  const isShortAnswer = item.question_profile === "short_answer";
  const correctOptionIndex = submissionResult?.correct_option_index ?? null;
  const selectedIndex =
    !isShortAnswer && submitted
      ? (submissionResult?.selected_option_index ?? null)
      : typeof selectedAnswer === "number"
        ? selectedAnswer
        : null;
  const submittedText =
    isShortAnswer && submitted ? (submissionResult?.selected_text ?? null) : null;

  const resultLabel =
    submissionResult == null
      ? "미응답"
      : submissionResult.is_correct
        ? "정답"
        : "오답";

  return (
    <section className="rounded-[32px] border border-slate-100 bg-white p-8 shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-500">
          {prompt.eyebrow}
        </span>
        <span
          className={`rounded-full border px-3 py-2 text-xs font-semibold ${getProfileAccentClass(item.question_profile)}`}
        >
          {getProfileLabel(item.question_profile)}
        </span>
      </div>

      <h1 className="mt-6 text-3xl font-black leading-tight tracking-tight text-slate-900">
        {prompt.title}
      </h1>
      <p className="mt-3 text-sm text-slate-500">{prompt.meta}</p>

      {isShortAnswer ? (
        <div className="mt-8">
          <textarea
            className={`w-full rounded-[20px] border-2 px-5 py-4 text-base leading-7 text-slate-800 outline-none transition resize-none ${
              submitted
                ? "border-slate-200 bg-slate-50 text-slate-500"
                : "border-violet-300 bg-white focus:border-violet-500"
            }`}
            disabled={submitted}
            onChange={(e) => onAnswer(e.target.value)}
            placeholder="답변을 입력하세요"
            rows={4}
            value={submitted ? (submittedText ?? "") : (typeof selectedAnswer === "string" ? selectedAnswer : "")}
          />
          {!submitted && !selectedAnswer ? (
            <p className="mt-3 text-sm font-semibold text-slate-500">현재 선택: 입력 없음</p>
          ) : null}
        </div>
      ) : (
        <div className="mt-8 grid gap-4">
          {item.options.map((option, optionIndex) => {
            const isSelected = selectedIndex === optionIndex;
            const isCorrect = submitted && correctOptionIndex === optionIndex;
            const isSelectedWrong = submitted && isSelected && !isCorrect;

            let cardClassName = "border-slate-200 bg-white text-slate-800 hover:border-orange-300";
            if (!submitted && isSelected) {
              cardClassName = "border-orange-400 bg-orange-50 text-slate-900";
            }
            if (submitted && isCorrect) {
              cardClassName = "border-green-500 bg-green-50 text-green-900";
            }
            if (submitted && isSelectedWrong) {
              cardClassName = "border-red-400 bg-red-50 text-red-900";
            }

            return (
              <button
                className={`flex w-full items-start gap-4 rounded-[24px] border-2 px-5 py-5 text-left transition ${cardClassName}`}
                disabled={submitted}
                key={`${item.question}-${optionIndex}`}
                onClick={() => onAnswer(optionIndex)}
                type="button"
              >
                <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-current text-xs font-bold">
                  {String.fromCharCode(65 + optionIndex)}
                </span>
                <div className="flex-1">
                  <p className="text-base font-semibold leading-7">{option}</p>
                  {!submitted && isSelected ? (
                    <p className="mt-2 text-xs font-semibold uppercase tracking-[0.24em] text-orange-700">
                      선택한 답
                    </p>
                  ) : null}
                  {submitted && isSelected ? (
                    <p className="mt-2 text-xs font-semibold uppercase tracking-[0.24em] text-slate-700">
                      내 답안
                    </p>
                  ) : null}
                  {submitted && isCorrect ? (
                    <p className="mt-2 text-xs font-semibold uppercase tracking-[0.24em] text-green-700">
                      정답
                    </p>
                  ) : null}
                </div>
              </button>
            );
          })}
          {!submitted && selectedIndex === null ? (
            <p className="mt-4 text-sm font-semibold text-slate-500">현재 선택: 선택 안 함</p>
          ) : null}
          {submitted && selectedIndex === null ? (
            <p className="mt-4 text-sm font-semibold text-amber-700">내 답안: 미응답</p>
          ) : null}
        </div>
      )}

      {submitted ? (
        <div className="mt-8 rounded-[24px] border border-orange-100 bg-orange-50 px-5 py-5">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-orange-600">
            제출 결과
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <MetadataRow label="채점 결과" value={resultLabel} />
            <MetadataRow
              label={isShortAnswer ? "모범 답안" : "정답"}
              value={
                isShortAnswer
                  ? (submissionResult?.answer_text_open ?? "정답 정보 없음")
                  : (submissionResult?.answer_text ?? "정답 정보 없음")
              }
            />
          </div>
          <p className="mt-5 text-xs font-semibold uppercase tracking-[0.24em] text-orange-600">
            해설
          </p>
          <p className="mt-3 text-sm leading-7 text-slate-700">
            {submissionResult?.explanation ?? "해설 정보가 없습니다."}
          </p>
        </div>
      ) : null}
    </section>
  );
}

function MetadataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] border border-orange-100 bg-white px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-slate-800">{value}</p>
    </div>
  );
}
