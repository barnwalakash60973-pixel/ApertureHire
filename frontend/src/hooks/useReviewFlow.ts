import { useCallback, useRef, useState } from "react";
import toast from "react-hot-toast";
import { submitReview, ReviewApiError } from "@/api/review";
import type { FinalReport } from "@/types/report";

export type FlowStage = "upload" | "processing" | "dashboard" | "error";

interface ReviewFlowState {
  stage: FlowStage;
  questionPaper: File | null;
  submission: File | null;
  report: FinalReport | null;
  errorMessage: string | null;
}

const initialState: ReviewFlowState = {
  stage: "upload",
  questionPaper: null,
  submission: null,
  report: null,
  errorMessage: null,
};

export function useReviewFlow() {
  const [state, setState] = useState<ReviewFlowState>(initialState);

  // Mirrors `state` after every render so analyze() (a stable, empty-deps
  // callback) can read the LATEST questionPaper/submission without a stale
  // closure - without needing to read them from inside a setState updater.
  const stateRef = useRef(state);
  stateRef.current = state;

  // Synchronous, render-independent lock against re-entrant submits (fast
  // double-clicks, etc).
  const isSubmittingRef = useRef(false);

  const setQuestionPaper = useCallback((file: File | null) => {
    setState((s) => ({ ...s, questionPaper: file }));
  }, []);

  const setSubmission = useCallback((file: File | null) => {
    setState((s) => ({ ...s, submission: file }));
  }, []);

  const analyze = useCallback(() => {
    if (isSubmittingRef.current) return; // already in flight - ignore repeat clicks

    const { questionPaper, submission } = stateRef.current;
    if (!questionPaper || !submission) return;

    isSubmittingRef.current = true;

    // IMPORTANT: setState updater functions must be pure - React 18
    // StrictMode calls them TWICE in development specifically to catch
    // side effects like network calls placed inside them. The network
    // call therefore lives here, in the callback body (which StrictMode
    // does NOT double-invoke), never inside a setState updater.
    setState((s) => ({ ...s, stage: "processing", errorMessage: null }));

    submitReview(questionPaper, submission)
      .then((res) => {
        setState((s) => ({ ...s, stage: "dashboard", report: res.report }));
      })
      .catch((err: unknown) => {
        const message =
          err instanceof ReviewApiError ? err.message : "Unexpected error during review.";
        toast.error(message);
        setState((s) => ({ ...s, stage: "error", errorMessage: message }));
      })
      .finally(() => {
        isSubmittingRef.current = false;
      });
  }, []);

  const reset = useCallback(() => setState(initialState), []);

  const retry = useCallback(() => {
    setState((s) => ({ ...s, stage: "upload", errorMessage: null }));
  }, []);

  return {
    ...state,
    canAnalyze: Boolean(state.questionPaper && state.submission),
    setQuestionPaper,
    setSubmission,
    analyze,
    reset,
    retry,
  };
}
