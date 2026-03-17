export type QuestionProfile = "basic_eval_4" | "review_5" | "retest_5";

export interface TopicAxis {
  label: string;
  supporting_terms: string[];
  evidence_chunk_ids: string[];
  source_corpus_ids: string[];
}

export interface WeeklyTopicSet {
  week_id: string;
  topic_axes: TopicAxis[];
  learning_paragraph: string;
}

export interface WeeklyGuide {
  week_id: string;
  learning_paragraph: string;
  topic_axes: TopicAxis[];
  review_points: string[];
  evidence_chunk_ids: string[];
}

export interface WeeklyQuizLearnerItem {
  item_id: string;
  question_profile: QuestionProfile;
  choice_count: 4 | 5;
  question: string;
  options: string[];
  difficulty: string;
  evidence_chunk_ids: string[];
  learning_goal: string;
  topic_axis_label: string;
  source_corpus_id: string;
  source_date: string;
  retrieved_chunk_ids: string[];
  learning_goal_source?: "metadata" | "generated";
}

export type AnswerMap = Record<string, number | null>;

export interface WeeklyQuizLearnerSet {
  week_id: string;
  mode: string;
  topic_axes: TopicAxis[];
  items: WeeklyQuizLearnerItem[];
  corpus_ids: string[];
  min_questions_per_corpus: number;
  model_info: Record<string, string>;
}

export interface WeeklyQuestionTypeMetric {
  question_profile: QuestionProfile | string;
  question_count: number;
  covered_topic_axes: string[];
}

export interface WeeklyTopicCoverage {
  topic_axis_label: string;
  question_count: number;
  supporting_terms: string[];
}

export interface WeeklyReport {
  week_id: string;
  question_type_metrics: WeeklyQuestionTypeMetric[];
  topic_coverage: WeeklyTopicCoverage[];
  mismatched_axis_item_count?: number;
  learning_goal_source_distribution?: Record<string, number>;
  notes: string[];
}

export interface WeeklyLearnerMemoFocusTopic {
  label: string;
  wrong_count: number;
}

export interface WeeklyLearnerMemoFocusDate {
  source_date: string;
  wrong_count: number;
}

export interface WeeklyLearnerMemo {
  status: "no_submission" | "all_correct" | "ready";
  headline: string;
  summary: string;
  recommended_review_points: string[];
  focus_topics: WeeklyLearnerMemoFocusTopic[];
  focus_dates: WeeklyLearnerMemoFocusDate[];
}

export interface WeeklyReportResponse extends WeeklyReport {
  learner_memo: WeeklyLearnerMemo;
}

export interface WeeklySelection {
  week_id: string;
  week: number;
  corpus_ids: string[];
  dates: string[];
  subject: string;
  content: string;
  learning_goal: string;
}

export interface WeeklyBundleApiResponse {
  topics: WeeklyTopicSet;
  guide: WeeklyGuide;
  quiz_set: WeeklyQuizLearnerSet;
  report: WeeklyReport;
}

export interface WeeklyBundlePayload {
  week: WeeklySelection;
  topics: WeeklyTopicSet;
  guide: WeeklyGuide;
  quiz: WeeklyQuizLearnerSet;
  report: WeeklyReport;
}

export interface WeeklyQuizSubmissionAnswer {
  item_id: string;
  selected_option_index: number;
}

export interface WeeklyQuizSubmissionRequest {
  answers: WeeklyQuizSubmissionAnswer[];
}

export interface WeeklyQuizSubmissionResult {
  item_id: string;
  selected_option_index: number | null;
  correct_option_index: number;
  answer_text: string;
  explanation: string;
  is_correct: boolean;
}

export interface WeeklyQuizSubmissionResponse {
  attempt_id: string;
  week_id: string;
  submitted_at: string;
  total_questions: number;
  correct_count: number;
  score: number;
  results: WeeklyQuizSubmissionResult[];
  learner_memo?: WeeklyLearnerMemo | null;
}

export interface WeeklyQuizReviewResult {
  item_id: string;
  question: string;
  options: string[];
  selected_option_index: number | null;
  correct_option_index: number;
  answer_text: string;
  explanation: string;
  is_correct: boolean;
  topic_axis_label: string;
  source_corpus_id: string;
  source_date: string;
  learning_goal: string;
  learning_goal_source?: "metadata" | "generated";
  retrieved_chunk_ids: string[];
  evidence_chunk_ids: string[];
}

export interface WeeklyQuizSubmissionDetailResponse {
  attempt_id: string;
  week_id: string;
  total_questions: number;
  correct_count: number;
  score: number;
  submitted_at: string;
  results: WeeklyQuizReviewResult[];
}

export interface ApiErrorPayload {
  detail?: string;
}
