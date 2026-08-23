export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function dimensionLabel(key: string): string {
  const labels: Record<string, string> = {
    requirement_coverage: "Requirement Coverage",
    technical_correctness: "Technical Correctness",
    ai_engineering: "AI Engineering",
    software_engineering: "Software Engineering",
    production_readiness: "Production Readiness",
    reasoning_depth: "Reasoning Depth",
  };
  return labels[key] ?? key;
}
