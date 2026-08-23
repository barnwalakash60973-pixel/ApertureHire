import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import toast from "react-hot-toast";
import { FiCheck, FiEdit2 } from "react-icons/fi";
import { Badge, Button, Card, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import { MultiFileDropzone } from "@/components/upload/MultiFileDropzone";
import { confirmImport, editCandidate, importResumes, listCandidates, CampaignApiError } from "@/api/campaigns";
import type { Candidate } from "@/types/campaign";

export function ResumeImportPage() {
  const { campaignId } = useParams<{ campaignId: string }>();
  const [files, setFiles] = useState<File[]>([]);
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const load = () => {
    if (!campaignId) return;
    listCandidates(campaignId)
      .then(setCandidates)
      .catch((err: unknown) => setError(err instanceof CampaignApiError ? err.message : "Failed to load candidates."));
  };

  useEffect(load, [campaignId]);

  const hasPendingReview = candidates?.some((c) => c.status === "pending_review") ?? false;

  const doImport = async () => {
    if (!campaignId || files.length === 0) return;
    setImporting(true);
    try {
      const result = await importResumes(campaignId, files);
      toast.success(`${result.total_uploaded} resumes imported - ${result.would_shortlist_count} would be shortlisted.`);
      setFiles([]);
      load();
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Import failed.");
    } finally {
      setImporting(false);
    }
  };

  const doConfirm = async () => {
    if (!campaignId) return;
    setConfirming(true);
    try {
      const result = await confirmImport(campaignId);
      toast.success(`Confirmed - ${result.shortlisted_count} shortlisted, ${result.emails_sent} shortlist emails sent.`);
      load();
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Confirm failed.");
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="mb-1 text-2xl font-semibold text-ink">Import resumes</h1>
      <p className="mb-8 text-sm text-ink-muted">
        Resumes are matched against the job description automatically (no AI - regex/dictionary skill + experience matching).
        Review extracted names/emails before confirming.
      </p>

      <Card className="mb-8 p-6">
        <MultiFileDropzone label="Upload resumes" hint="Drop .docx/.pdf files, or click to browse" files={files} onFilesChange={setFiles} />
        <div className="mt-4">
          <Button onClick={doImport} disabled={files.length === 0 || importing}>
            {importing ? "Importing..." : `Import ${files.length || ""} resume(s)`}
          </Button>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={load} />}

      {!error && candidates === null && <Skeleton className="h-40 w-full" />}

      {!error && candidates !== null && candidates.length === 0 && (
        <EmptyState title="No candidates yet" description="Upload resumes above to get started." />
      )}

      {!error && candidates !== null && candidates.length > 0 && (
        <>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">Candidates ({candidates.length})</h2>
            {hasPendingReview && (
              <Button onClick={doConfirm} disabled={confirming}>
                <FiCheck size={15} /> {confirming ? "Confirming..." : "Confirm import"}
              </Button>
            )}
          </div>
          <div className="space-y-2.5">
            {candidates.map((c) => (
              <CandidateRow key={c.id} candidate={c} campaignId={campaignId!} onUpdated={load} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function decisionBadgeColor(status: string): string {
  if (status === "shortlisted" || status.startsWith("final_selected")) return "#1FB37A";
  if (status === "not_shortlisted" || status.startsWith("final_rejected")) return "#E24E4E";
  if (status === "pending_review") return "var(--color-ink-muted)";
  return "#5FBF6E";
}

function CandidateRow({ candidate, campaignId, onUpdated }: { candidate: Candidate; campaignId: string; onUpdated: () => void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(candidate.name ?? "");
  const [email, setEmail] = useState(candidate.email ?? "");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await editCandidate(campaignId, candidate.id, { name: name.trim() || undefined, email: email.trim() || undefined });
      toast.success("Candidate updated.");
      setEditing(false);
      onUpdated();
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Update failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          {editing ? (
            <div className="flex flex-wrap gap-2">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Name"
                className="min-w-0 flex-1 rounded-lg border border-base-border bg-base-surface2 px-3 py-1.5 text-sm text-ink outline-none focus:border-signal"
              />
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                className="min-w-0 flex-1 rounded-lg border border-base-border bg-base-surface2 px-3 py-1.5 text-sm text-ink outline-none focus:border-signal"
              />
              <Button size="sm" onClick={save} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <p className="font-medium text-ink">{candidate.name ?? <span className="italic text-ink-faint">Not Found</span>}</p>
              <button onClick={() => setEditing(true)} className="text-ink-faint hover:text-ink" aria-label="Edit">
                <FiEdit2 size={12} />
              </button>
            </div>
          )}
          {!editing && <p className="mt-0.5 text-xs text-ink-muted">{candidate.email ?? <span className="italic text-ink-faint">Not Found</span>}</p>}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Badge color={decisionBadgeColor(candidate.status)}>{candidate.status.replace(/_/g, " ")}</Badge>
        </div>
      </div>

      {candidate.match_result && (
        <div className="mt-3 border-t border-base-border pt-3 text-xs text-ink-muted">
          <p>{candidate.match_result.decision_reason}</p>
          {candidate.match_result.missing_skills.length > 0 && (
            <p className="mt-1">
              Missing: <span className="text-ink">{candidate.match_result.missing_skills.join(", ")}</span>
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
