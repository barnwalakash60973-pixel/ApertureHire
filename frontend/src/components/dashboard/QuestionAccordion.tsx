import { useState } from "react";
import { FiChevronDown } from "react-icons/fi";
import { Badge, Card } from "@/components/ui/primitives";
import { dimensionLabel } from "@/lib/utils";
import { scoreToColor, severityLabel, ISSUE_TYPE_LABELS } from "@/lib/recommendation";
import type { QuestionReview } from "@/types/report";

const STATUS_META: Record<string, { label: string; color: string }> = {
  answered: { label: "Answered", color: "#1FB37A" },
  partially_answered: { label: "Partial", color: "#D9A62E" },
  unanswered: { label: "Unanswered", color: "#E24E4E" },
};

export function QuestionAccordion({ review }: { review: QuestionReview }) {
  const [open, setOpen] = useState(false);
  const status = STATUS_META[review.answer.status] ?? STATUS_META.unanswered;
  const avg =
    Object.values(review.scores).reduce((a, b) => a + b, 0) /
    Object.values(review.scores).length;

  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
      >
        <div className="flex min-w-0 items-center gap-3">
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-xs font-semibold"
            style={{ backgroundColor: `${scoreToColor(avg)}1A`, color: scoreToColor(avg) }}
          >
            {review.question.number}
          </span>
          <p className="truncate text-sm font-medium text-ink">{review.question.text}</p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Badge color={status.color}>{status.label}</Badge>
          <span className="tabular-nums text-sm font-semibold text-ink-muted">
            {avg.toFixed(1)}
          </span>
          <FiChevronDown
            className={`text-ink-faint transition-transform ${open ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {open && (
        <div className="space-y-5 border-t border-base-border px-5 py-5">
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ink-faint">
              Candidate answer
            </p>
            <p className="whitespace-pre-wrap rounded-lg bg-base-surface2 p-3 text-sm text-ink-muted">
              {review.answer.text || "No answer provided."}
            </p>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-faint">
              Dimension scores
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(review.scores).map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-center justify-between rounded-lg bg-base-surface2 px-3 py-2"
                >
                  <span className="text-xs text-ink-muted">{dimensionLabel(key)}</span>
                  <span
                    className="tabular-nums text-xs font-semibold"
                    style={{ color: scoreToColor(value) }}
                  >
                    {value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {review.strengths.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ink-faint">
                Strengths
              </p>
              <ul className="space-y-1">
                {review.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-ink-muted before:content-['+_'] before:text-grade-strong_hire before:font-semibold">
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {review.issues.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ink-faint">
                Issues
              </p>
              <ul className="space-y-2">
                {review.issues.map((issue, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2.5 rounded-lg bg-base-surface2 p-3"
                  >
                    <Badge color={issue.severity >= 5 ? "#E24E4E" : issue.severity >= 3 ? "#D9A62E" : "#8B8FA3"}>
                      {severityLabel(issue.severity)}
                    </Badge>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-ink">
                        {ISSUE_TYPE_LABELS[issue.type] ?? issue.type}
                      </p>
                      <p className="mt-0.5 text-xs text-ink-muted">{issue.description}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ink-faint">
              Summary
            </p>
            <p className="text-sm text-ink-muted">{review.summary}</p>
          </div>
        </div>
      )}
    </Card>
  );
}
