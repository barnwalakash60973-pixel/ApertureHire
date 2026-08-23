/**
 * Mirrors app/domain/models.py and app/domain/enums.py exactly.
 * Keep in sync with the backend — these are not independently guessed types.
 */

export type AnswerStatus = "answered" | "partially_answered" | "unanswered";

export type IssueType =
  | "missing_subquestion"
  | "weak_explanation"
  | "hallucination"
  | "incorrect_azure_architecture"
  | "missing_production_concerns"
  | "weak_rag_design"
  | "weak_agent_architecture"
  | "weak_evaluation_framework"
  | "other";

export type HiringRecommendation =
  | "strong_hire"
  | "hire"
  | "lean_hire"
  | "no_hire"
  | "strong_no_hire";

export interface Question {
  id: string;
  section: string;
  number: string;
  text: string;
  subquestions: string[];
}

export interface Answer {
  question_id: string | null;
  text: string;
  status: AnswerStatus;
}

export interface DimensionScores {
  requirement_coverage: number;
  technical_correctness: number;
  ai_engineering: number;
  software_engineering: number;
  production_readiness: number;
  reasoning_depth: number;
}

export interface Issue {
  type: IssueType;
  description: string;
  severity: number; // 1-5
}

export interface QuestionReview {
  question: Question;
  answer: Answer;
  scores: DimensionScores;
  issues: Issue[];
  strengths: string[];
  summary: string;
}

export interface SectionReport {
  section: string;
  question_reviews: QuestionReview[];
}

export interface ReportStatistics {
  questions: number;
  answered: number;
  unanswered: number;
  critical_issues: number;
}

export type ScoreBreakdown = Partial<Record<keyof DimensionScores, number>>;

export interface FinalReport {
  overall_score: number;
  section_reports: SectionReport[];
  missing_topics: string[];
  improvements: string[];
  hiring_recommendation: HiringRecommendation;
  hiring_rationale: string;
  score_breakdown: ScoreBreakdown;
  statistics: ReportStatistics;
}

export interface ReviewResponse {
  report: FinalReport;
}

export interface ApiErrorBody {
  error?: string;
  detail?: string;
}
