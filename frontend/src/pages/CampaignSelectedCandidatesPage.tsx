import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { FiAward, FiDownload, FiXCircle } from "react-icons/fi";
import { Badge, Card, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import {
  downloadCandidateReport,
  downloadCandidateReportPdf,
  downloadCandidateResume,
  downloadCandidateSubmission,
  listSelectedCandidates,
  CampaignApiError,
} from "@/api/campaigns";
import type { SelectedCandidate } from "@/types/campaign";
import toast from "react-hot-toast";

function recommendationColor(rec: string): string {
  if (rec === "strong_hire") return "#1FB37A";
  if (rec === "hire") return "#5FBF6E";
  if (rec === "lean_hire") return "#D9A62E";
  return "var(--color-ink-muted)";
}

function DownloadAction({ available, label, onDownload }: { available: boolean; label: string; onDownload: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);

  if (!available) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-ink-faint" title={`${label} not available`}>
        <FiXCircle size={13} /> {label}
      </span>
    );
  }

  const handleClick = async () => {
    setBusy(true);
    try {
      await onDownload();
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : `Failed to download ${label.toLowerCase()}.`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className="inline-flex items-center gap-1 text-xs text-ink-muted transition-colors hover:text-signal disabled:opacity-50"
      title={`Download ${label}`}
    >
      <FiDownload size={13} className={busy ? "animate-pulse" : ""} /> {label}
    </button>
  );
}

export function CampaignSelectedCandidatesPage() {
  const { campaignId } = useParams<{ campaignId: string }>();
  const [candidates, setCandidates] = useState<SelectedCandidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    if (!campaignId) return;
    setError(null);
    listSelectedCandidates(campaignId)
      .then(setCandidates)
      .catch((err: unknown) => setError(err instanceof CampaignApiError ? err.message : "Failed to load selected candidates."));
  };

  useEffect(load, [campaignId]);

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-ink">Selected candidates</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Ranked highest score to lowest. Only candidates who cleared the hiring threshold appear here.
        </p>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && candidates === null && (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      )}
      {!error && candidates !== null && candidates.length === 0 && (
        <EmptyState title="No selected candidates yet" description="This list fills in once evaluations mark candidates as final selected." />
      )}

      {!error && candidates !== null && candidates.length > 0 && (
        <div className="space-y-3">
          {candidates.map((c) => (
            <Card key={c.id} className="p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-signal/10 text-sm font-semibold text-signal">
                    {c.rank === 1 ? <FiAward size={16} /> : `#${c.rank}`}
                  </div>
                  <div>
                    <p className="font-medium text-ink">{c.name ?? "Unnamed candidate"}</p>
                    <p className="text-xs text-ink-muted">{c.email}</p>
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl font-semibold text-ink">
                      {c.overall_score.toFixed(1)} <span className="text-sm font-normal text-ink-faint">/ 10</span>
                    </span>
                    <Badge color={recommendationColor(c.hiring_recommendation)}>{c.hiring_recommendation.replace(/_/g, " ")}</Badge>
                  </div>
                  <p className="text-xs text-ink-muted">
                    Rank #{c.rank} of {candidates?.length ?? c.rank}
                  </p>
                </div>
              </div>

              {(c.strengths.length > 0 || c.weaknesses.length > 0) && (
                <div className="mt-4 grid grid-cols-1 gap-3 border-t border-base-border pt-4 sm:grid-cols-2">
                  {c.strengths.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-xs font-medium text-ink-muted">Strengths</p>
                      <div className="flex flex-wrap gap-1.5">
                        {c.strengths.map((s, i) => (
                          <Badge key={i} color="#1FB37A">{s}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {c.weaknesses.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-xs font-medium text-ink-muted">Weaknesses</p>
                      <div className="flex flex-wrap gap-1.5">
                        {c.weaknesses.map((w, i) => (
                          <Badge key={i} color="#E27A3F">{w}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="mt-4 flex items-center gap-4 border-t border-base-border pt-3">
                <DownloadAction
                  available={c.resume_available}
                  label="Resume"
                  onDownload={() => downloadCandidateResume(campaignId!, c.id, c.name)}
                />
                <DownloadAction
                  available={c.submission_available}
                  label="Submission"
                  onDownload={() => downloadCandidateSubmission(campaignId!, c.id, c.name)}
                />
                <DownloadAction
                  available={c.report_available}
                  label="Report"
                  onDownload={() => downloadCandidateReport(campaignId!, c.id, c.name)}
                />
                <DownloadAction
                  available={c.report_available}
                  label="Report (PDF)"
                  onDownload={() => downloadCandidateReportPdf(campaignId!, c.id, c.name)}
                />
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
