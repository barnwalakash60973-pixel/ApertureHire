import { FiAlertTriangle, FiCheckCircle, FiHelpCircle, FiList } from "react-icons/fi";
import { Card } from "@/components/ui/primitives";
import type { ReportStatistics } from "@/types/report";

export function AnalyticsCards({ statistics }: { statistics: ReportStatistics }) {
  const items = [
    { label: "Questions", value: statistics.questions, icon: FiList, tint: "var(--color-signal)" },
    { label: "Answered", value: statistics.answered, icon: FiCheckCircle, tint: "#1FB37A" },
    { label: "Unanswered", value: statistics.unanswered, icon: FiHelpCircle, tint: "#D9A62E" },
    {
      label: "Critical Issues",
      value: statistics.critical_issues,
      icon: FiAlertTriangle,
      tint: "#E24E4E",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {items.map(({ label, value, icon: Icon, tint }) => (
        <Card key={label} className="p-5">
          <div
            className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg"
            style={{ backgroundColor: `${tint}1A`, color: tint }}
          >
            <Icon size={16} />
          </div>
          <p className="tabular-nums text-2xl font-semibold text-ink">{value}</p>
          <p className="text-xs text-ink-muted">{label}</p>
        </Card>
      ))}
    </div>
  );
}
