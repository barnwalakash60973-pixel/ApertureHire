import { FiAlertCircle, FiDownload, FiTarget } from "react-icons/fi";
import { Card, Button, EmptyState } from "@/components/ui/primitives";
import type { FinalReport } from "@/types/report";

export function ImprovementsPanel({ improvements }: { improvements: string[] }) {
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center gap-2">
        <FiTarget className="text-signal" size={15} />
        <h3 className="text-sm font-semibold text-ink">Top Improvements</h3>
      </div>
      {improvements.length === 0 ? (
        <p className="text-sm text-ink-muted">No significant issues found.</p>
      ) : (
        <ul className="space-y-2.5">
          {improvements.map((item, i) => (
            <li key={i} className="text-sm leading-relaxed text-ink-muted">
              <span className="mr-2 text-ink-faint">{i + 1}.</span>
              {item}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function MissingTopicsPanel({ topics }: { topics: string[] }) {
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center gap-2">
        <FiAlertCircle className="text-grade-lean_hire" size={15} />
        <h3 className="text-sm font-semibold text-ink">Missing Topics</h3>
      </div>
      {topics.length === 0 ? (
        <p className="text-sm text-ink-muted">Every question was answered.</p>
      ) : (
        <ul className="space-y-2">
          {topics.map((topic, i) => (
            <li
              key={i}
              className="rounded-lg bg-base-surface2 px-3 py-2 text-sm text-ink-muted"
            >
              {topic}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function ExportButton({ report }: { report: FinalReport }) {
  const handleExport = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "assignment-review.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex gap-2">
      <Button variant="secondary" onClick={handleExport}>
        <FiDownload size={14} /> Download JSON
      </Button>
      <Button variant="ghost" disabled title="Coming soon">
        Download PDF
      </Button>
    </div>
  );
}

export function DashboardEmptyState() {
  return (
    <EmptyState
      title="No report yet"
      description="Upload a question paper and a submission to generate a review."
    />
  );
}
