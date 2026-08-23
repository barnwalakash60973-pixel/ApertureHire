import { ScoreGauge } from "./ScoreGauge";
import { Card, Badge } from "@/components/ui/primitives";
import { getTierMeta } from "@/lib/recommendation";
import type { FinalReport } from "@/types/report";

export function HeroScoreCard({ report }: { report: FinalReport }) {
  const tier = getTierMeta(report.hiring_recommendation);
  const percentage = Math.round((report.overall_score / 10) * 100);

  return (
    <Card className="relative overflow-hidden p-8">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.08]"
        style={{
          background: `radial-gradient(600px circle at 15% 20%, ${tier.color}, transparent 60%)`,
        }}
      />
      <div className="relative flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-6">
          <ScoreGauge score={report.overall_score} />
          <div>
            <p className="text-xs uppercase tracking-wide text-ink-faint">
              Overall assessment
            </p>
            <div className="mt-1.5">
              <Badge color={tier.color} className="text-sm px-3 py-1.5">
                {tier.label}
              </Badge>
            </div>
            <p className="mt-2 max-w-sm text-sm text-ink-muted">
              {report.hiring_rationale}
            </p>
          </div>
        </div>
        <div className="text-center sm:text-right">
          <p className="tabular-nums text-4xl font-semibold text-ink">{percentage}%</p>
          <p className="text-xs text-ink-faint">overall percentage</p>
        </div>
      </div>
    </Card>
  );
}
