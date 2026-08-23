import type { HiringRecommendation } from "@/types/report";

interface TierMeta {
  label: string;
  color: string; // matches grade.* in tailwind.config.js
  description: string;
}

const TIER_META: Record<HiringRecommendation, TierMeta> = {
  strong_hire: {
    label: "Strong Hire",
    color: "#1FB37A",
    description: "Excellent performance across the board.",
  },
  hire: {
    label: "Hire",
    color: "#5FBF6E",
    description: "Solid understanding, minor gaps only.",
  },
  lean_hire: {
    label: "Lean Hire",
    color: "#D9A62E",
    description: "Shows potential, needs mentoring.",
  },
  no_hire: {
    label: "No Hire",
    color: "#E27A3F",
    description: "Below the expected technical bar.",
  },
  strong_no_hire: {
    label: "Strong No Hire",
    color: "#E24E4E",
    description: "Significant gaps or incorrect fundamentals.",
  },
};

export function getTierMeta(rec: HiringRecommendation): TierMeta {
  return TIER_META[rec];
}

/** Maps a 0-10 score to a point on the same red -> green grade spectrum. */
export function scoreToColor(score: number): string {
  const clamped = Math.max(0, Math.min(10, score));
  const stops = [
    { at: 0, color: [226, 78, 78] }, // red
    { at: 4, color: [226, 122, 63] }, // orange
    { at: 5.5, color: [217, 166, 46] }, // amber
    { at: 7, color: [95, 191, 110] }, // green
    { at: 8.5, color: [31, 179, 122] }, // deep emerald
  ];
  let lower = stops[0];
  let upper = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (clamped >= stops[i].at && clamped <= stops[i + 1].at) {
      lower = stops[i];
      upper = stops[i + 1];
      break;
    }
  }
  const span = upper.at - lower.at || 1;
  const t = (clamped - lower.at) / span;
  const rgb = lower.color.map((c, i) => Math.round(c + (upper.color[i] - c) * t));
  return `rgb(${rgb.join(",")})`;
}

export function severityLabel(severity: number): string {
  if (severity >= 5) return "Critical";
  if (severity >= 3) return "Notable";
  return "Minor";
}

export const ISSUE_TYPE_LABELS: Record<string, string> = {
  missing_subquestion: "Missing sub-question",
  weak_explanation: "Weak explanation",
  hallucination: "Hallucination",
  incorrect_azure_architecture: "Incorrect architecture",
  missing_production_concerns: "Missing production concerns",
  weak_rag_design: "Weak RAG design",
  weak_agent_architecture: "Weak agent architecture",
  weak_evaluation_framework: "Weak evaluation framework",
  other: "Other",
};
