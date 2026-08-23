import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import toast from "react-hot-toast";
import { FiCheckCircle, FiClock, FiExternalLink, FiUploadCloud } from "react-icons/fi";
import { Badge, Button, Card, ErrorState, Skeleton } from "@/components/ui/primitives";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { getSubmissionView, submitSolution } from "@/api/submission";
import { CampaignApiError } from "@/api/campaigns";
import type { SubmissionView } from "@/types/campaign";

/**
 * Candidate-facing portal at /submission/:token - NO login, access is the
 * token itself. Deliberately shows none of: match score, AI evaluation
 * score, hiring recommendation, ranking, other candidates, internal HR
 * notes - the backend's SubmissionViewResponse never returns any of that,
 * so there's nothing here that could leak it.
 */
export function SubmissionPortalPage() {
  const { token } = useParams<{ token: string }>();
  const [view, setView] = useState<SubmissionView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    if (!token) return;
    setLoading(true);
    getSubmissionView(token)
      .then((v) => {
        setView(v);
        setError(null);
      })
      .catch((err) => setError(err instanceof CampaignApiError ? err.message : "Could not load your assignment."))
      .finally(() => setLoading(false));
  };

  useEffect(load, [token]);

  const doSubmit = async () => {
    if (!token || !file) return;
    setSubmitting(true);
    try {
      await submitSolution(token, file);
      toast.success("Solution submitted.");
      setFile(null);
      load();
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-10">
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !view) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-10">
        <ErrorState message={error ?? "This submission link is invalid or has expired."} />
      </div>
    );
  }

  // Only one submission is ever allowed - once the candidate has
  // submitted, the portal is read-only (no resubmission, even before
  // evaluation starts).
  const canSubmit = view.status === "not_submitted";

  const statusMeta: Record<SubmissionView["status"], { label: string; color: string }> = {
    not_submitted: { label: "Not Submitted", color: "#D9A62E" },
    submitted: { label: "Submitted", color: "#1FB37A" },
    waiting_for_evaluation: { label: "Submitted", color: "#1FB37A" },
    overdue: { label: "Deadline Passed", color: "#D64545" },
    evaluated: { label: "Under Review", color: "#4C6FFF" },
  };
  const meta = statusMeta[view.status];

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <p className="mb-1 text-sm text-ink-muted">Welcome, {view.candidate_name || "Candidate"}</p>
      <h1 className="mb-1 text-2xl font-semibold text-ink">{view.assignment_title}</h1>
      <p className="mb-6 text-sm text-ink-muted">{view.campaign_name}</p>

      <Card className="mb-6 space-y-4 p-6">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-ink">Status</span>
          <Badge color={meta.color}>{meta.label}</Badge>
        </div>

        {view.deadline && (
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <FiClock size={14} />
            Deadline: {new Date(view.deadline).toLocaleString()}
          </div>
        )}

        {view.submitted_on && (
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <FiCheckCircle size={14} />
            Submitted: {new Date(view.submitted_on).toLocaleString()}
          </div>
        )}

        <a href={view.assignment_link} target="_blank" rel="noreferrer">
          <Button size="sm" variant="secondary">
            <FiExternalLink size={13} /> {view.assignment_is_drive_link ? "Open Assignment (Google Drive)" : "Download Assignment"}
          </Button>
        </a>
      </Card>

      {view.status === "evaluated" && (
        <Card className="mb-6 p-6 text-sm text-ink-muted">Your submission has been evaluated. Our team will reach out with next steps.</Card>
      )}

      {view.status === "waiting_for_evaluation" && (
        <Card className="mb-6 p-6 text-sm text-ink-muted">
          Your solution has been submitted and is awaiting evaluation. Only one submission is accepted per candidate, so this can't be changed.
        </Card>
      )}

      {view.status === "overdue" && (
        <Card className="mb-6 p-6 text-sm text-ink-muted">The submission deadline has passed. If you believe this is an error, please contact HR directly.</Card>
      )}

      {canSubmit && (
        <Card className="space-y-4 p-6">
          <h2 className="text-sm font-semibold text-ink">Upload your solution</h2>
          <p className="text-xs text-ink-muted">You can only submit once, so make sure your file is final before uploading.</p>
          <FileDropzone label="Upload solution" hint=".docx/.pdf/.zip" file={file} onFileChange={setFile} accept={[".pdf", ".docx", ".zip"]} />
          <Button onClick={doSubmit} disabled={submitting || !file}>
            <FiUploadCloud size={14} /> {submitting ? "Submitting..." : "Submit solution"}
          </Button>
        </Card>
      )}
    </div>
  );
}
