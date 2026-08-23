import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/primitives";
import { dimensionLabel } from "@/lib/utils";
import { scoreToColor } from "@/lib/recommendation";
import type { ScoreBreakdown } from "@/types/report";

export function ScoreBreakdownChart({ breakdown }: { breakdown: ScoreBreakdown }) {
  const data = Object.entries(breakdown).map(([key, value]) => ({
    key,
    label: dimensionLabel(key),
    score: value ?? 0,
  }));

  if (data.length === 0) return null;

  return (
    <Card className="p-6">
      <h3 className="mb-4 text-sm font-semibold text-ink">Score Breakdown</h3>
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, 10]}
              tick={{ fill: "var(--color-ink-muted)", fontSize: 12 }}
              axisLine={{ stroke: "var(--color-border)" }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={140}
              tick={{ fill: "var(--color-ink-muted)", fontSize: 12 }}
              axisLine={{ stroke: "var(--color-border)" }}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: "var(--color-surface-2)" }}
              contentStyle={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                fontSize: 12,
                color: "var(--color-ink)",
              }}
              formatter={(value: number) => [value.toFixed(2), "Score"]}
            />
            <Bar dataKey="score" radius={[0, 6, 6, 0]} barSize={18}>
              {data.map((d) => (
                <Cell key={d.key} fill={scoreToColor(d.score)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
