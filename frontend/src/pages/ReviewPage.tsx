import { AnimatePresence, motion } from "framer-motion";
import { FiArrowRight, FiRefreshCw } from "react-icons/fi";
import { useReviewFlow } from "@/hooks/useReviewFlow";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { ProcessingSteps } from "@/components/processing/ProcessingSteps";
import { Button, ErrorState } from "@/components/ui/primitives";
import { HeroScoreCard } from "@/components/dashboard/HeroScoreCard";
import { AnalyticsCards } from "@/components/dashboard/AnalyticsCards";
import { ScoreBreakdownChart } from "@/components/dashboard/ScoreBreakdownChart";
import { QuestionAccordion } from "@/components/dashboard/QuestionAccordion";
import {
  ExportButton,
  ImprovementsPanel,
  MissingTopicsPanel,
} from "@/components/dashboard/ReportPanels";

function FadeStage({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.3 }}
    >
      {children}
    </motion.div>
  );
}

export function ReviewPage() {
  const flow = useReviewFlow();

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <AnimatePresence mode="wait">
        {flow.stage === "upload" && (
          <FadeStage key="upload">
            <div className="mb-8 text-center">
              <h1 className="text-2xl font-semibold text-ink">Upload the assignment</h1>
              <p className="mt-1.5 text-sm text-ink-muted">
                Both the question paper and the candidate's submission are required.
              </p>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <FileDropzone
                label="Question paper"
                hint="PDF or DOCX, up to 15MB"
                file={flow.questionPaper}
                onFileChange={flow.setQuestionPaper}
              />
              <FileDropzone
                label="Candidate submission"
                hint="PDF or DOCX, up to 15MB"
                file={flow.submission}
                onFileChange={flow.setSubmission}
              />
            </div>
            <div className="mt-8 flex justify-center">
              <Button
                disabled={!flow.canAnalyze || flow.stage !== "upload"}
                onClick={flow.analyze}
                size="lg"
              >
                Analyze assignment <FiArrowRight size={16} />
              </Button>
            </div>
          </FadeStage>
        )}

        {flow.stage === "processing" && (
          <FadeStage key="processing">
            <div className="py-16">
              <ProcessingSteps />
            </div>
          </FadeStage>
        )}

        {flow.stage === "error" && (
          <FadeStage key="error">
            <ErrorState
              message={flow.errorMessage ?? "Unknown error."}
              onRetry={flow.retry}
            />
          </FadeStage>
        )}

        {flow.stage === "dashboard" && flow.report && (
          <FadeStage key="dashboard">
            <div className="mb-6 flex items-center justify-between">
              <h1 className="text-2xl font-semibold text-ink">Review results</h1>
              <div className="flex items-center gap-2">
                <ExportButton report={flow.report} />
                <Button variant="ghost" onClick={flow.reset}>
                  <FiRefreshCw size={14} /> New review
                </Button>
              </div>
            </div>

            <div className="space-y-6">
              <HeroScoreCard report={flow.report} />
              <AnalyticsCards statistics={flow.report.statistics} />

              <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
                <ScoreBreakdownChart breakdown={flow.report.score_breakdown} />
                <div className="space-y-6">
                  <ImprovementsPanel improvements={flow.report.improvements} />
                  <MissingTopicsPanel topics={flow.report.missing_topics} />
                </div>
              </div>

              <div>
                <h2 className="mb-3 text-sm font-semibold text-ink">Question Reviews</h2>
                <div className="space-y-3">
                  {flow.report.section_reports.map((section) => (
                    <div key={section.section}>
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-faint">
                        {section.section}
                      </p>
                      <div className="space-y-3">
                        {section.question_reviews.map((qr) => (
                          <QuestionAccordion key={qr.question.id} review={qr} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </FadeStage>
        )}
      </AnimatePresence>
    </div>
  );
}
