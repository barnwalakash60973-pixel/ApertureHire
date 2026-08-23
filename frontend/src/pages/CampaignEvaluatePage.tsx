import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import toast from "react-hot-toast";
import { FiAward, FiCheck, FiPlay, FiX } from "react-icons/fi";
import { Badge, Button, Card, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import {
  approveEvaluation,
  decideCandidate,
  evaluateCampaign,
  listCandidates,
  listPendingApprovalCandidates,
  CampaignApiError,
} from "@/api/campaigns";
import type { Candidate, SelectedCandidate } from "@/types/campaign";

function statusColor(status: string): string {
  if (status === "final_selected") return "#1FB37A";
  if (status === "final_rejected") return "#E24E4E";
  if (status === "pending_approval") return "#D9A62E";
  if (status === "submission_overdue") return "#E27A3F";
  if (status === "submitted") return "#5FBF6E";
  return "var(--color-ink-muted)";
}

function recommendationColor(rec: string): string {
  if (rec === "strong_hire") return "#1FB37A";
  if (rec === "hire") return "#5FBF6E";
  if (rec === "lean_hire") return "#D9A62E";
  return "var(--color-ink-muted)";
}

export function CampaignEvaluatePage() {
  const { campaignId } = useParams<{ campaignId: string }>();
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [pending, setPending] = useState<SelectedCandidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const load = () => {
    if (!campaignId) return;
    setError(null);
    listCandidates(campaignId)
      .then((all) => setCandidates(all.filter((c) => c.status !== "pending_review" && c.status !== "not_shortlisted")))
      .catch((err: unknown) => setError(err instanceof CampaignApiError ? err.message : "Failed to load candidates."));
    listPendingApprovalCandidates(campaignId)
      .then(setPending)
      .catch((err: unknown) => setError(err instanceof CampaignApiError ? err.message : "Failed to load pending approvals."));
  };

  useEffect(load, [campaignId]);

  const submittedCount = candidates?.filter((c) => c.status === "submitted").length ?? 0;

  const doEvaluate = async () => {
    if (!campaignId) return;
    setEvaluating(true);
    try {
      const result = await evaluateCampaign(campaignId);
      if (result.evaluated_count === 0) {
        toast("No submitted candidates to evaluate yet.");
      } else if (result.pending_selected_count + result.pending_rejected_count === 0) {
        toast.success(`Evaluated ${result.evaluated_count} candidate(s). Review and decide below.`);
      } else {
        toast.success(
          `Evaluated ${result.evaluated_count} - ${result.pending_selected_count} pending selection, ${result.pending_rejected_count} pending rejection. Review below before sending results.`
        );
      }
      load();
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Evaluation failed.");
    } finally {
      setEvaluating(false);
    }
  };

  const doApprove = async () => {
    if (!campaignId || !pending || pending.length === 0) return;
    if (!window.confirm(`Send final results to ${pending.length} candidate(s)? This emails everyone in the list below and cannot be undone.`)) {
      return;
    }
    setApproving(true);
    try {
      const result = await approveEvaluation(campaignId);
      toast.success(`Sent: ${result.final_selected_count} selected, ${result.final_rejected_count} rejected (${result.emails_sent} emails).`);
      load();
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Approval failed.");
    } finally {
      setApproving(false);
    }
  };

  const doDecide = async (candidateId: string, decision: "select" | "reject") => {
    if (!campaignId) return;
    setDecidingId(candidateId);
    try {
      await decideCandidate(campaignId, candidateId, decision);
      toast.success(decision === "select" ? "Candidate selected and emailed." : "Candidate rejected and emailed.");
      load();
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Failed to update decision.");
    } finally {
      setDecidingId(null);
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Evaluate</h1>
          <p className="mt-1 text-sm text-ink-muted">
            The only step that uses the LLM - extraction, matching, and scoring, once per submitted candidate.
          </p>
        </div>
        <Button onClick={doEvaluate} disabled={evaluating || submittedCount === 0}>
          <FiPlay size={14} /> {evaluating ? "Evaluating..." : `Evaluate ${submittedCount || ""} submission(s)`}
        </Button>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && candidates === null && <Skeleton className="h-40 w-full" />}
      {!error && candidates !== null && candidates.length === 0 && (
        <EmptyState title="No candidates yet" description="Candidates appear here once the assignment has been sent." />
      )}

      {!error && candidates !== null && candidates.length > 0 && (
        <div className="space-y-2.5">
          {candidates.map((c) => (
            <Card key={c.id} className="flex items-center justify-between px-5 py-3.5">
              <div>
                <p className="font-medium text-ink">{c.name ?? "Unnamed candidate"}</p>
                <p className="text-xs text-ink-muted">{c.email}</p>
              </div>
              <Badge color={statusColor(c.status)}>{c.status.replace(/_/g, " ")}</Badge>
            </Card>
          ))}
        </div>
      )}

      {pending !== null && pending.length > 0 && (
        <div className="mt-10">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-ink">Awaiting your approval</h2>
              <p className="mt-1 text-sm text-ink-muted">
                Computed outcome from the last evaluation run. Nothing has been emailed yet - review each candidate,
                override any of them if needed, then send.
              </p>
            </div>
            <Button onClick={doApprove} disabled={approving}>
              <FiCheck size={14} /> {approving ? "Sending..." : `Approve & Send (${pending.length})`}
            </Button>
          </div>

          <div className="space-y-3">
            {pending.map((c) => (
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
                    <Badge color={c.pending_decision === "select" ? "#1FB37A" : "#E24E4E"}>
                      Pending: {c.pending_decision === "select" ? "Select" : "Reject"}
                    </Badge>
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-3 border-t border-base-border pt-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={decidingId === c.id}
                    onClick={() => doDecide(c.id, "select")}
                  >
                    <FiCheck size={13} /> Select
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={decidingId === c.id}
                    onClick={() => doDecide(c.id, "reject")}
                  >
                    <FiX size={13} /> Reject
                  </Button>
                  <span className="text-xs text-ink-faint">Overriding sends that candidate's email immediately.</span>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
