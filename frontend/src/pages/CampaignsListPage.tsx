import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { FiArrowRight, FiPlus } from "react-icons/fi";
import { Badge, Button, Card, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { createCampaign, listCampaigns, CampaignApiError } from "@/api/campaigns";
import type { Campaign } from "@/types/campaign";

export function CampaignsListPage() {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setError(null);
    listCampaigns()
      .then(setCampaigns)
      .catch((err: unknown) => setError(err instanceof CampaignApiError ? err.message : "Failed to load campaigns."));
  };

  useEffect(load, []);

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Campaigns</h1>
          <p className="mt-1 text-sm text-ink-muted">Create a campaign, import resumes, and manage the hiring pipeline.</p>
        </div>
        <Button onClick={() => setShowCreate((v) => !v)}>
          <FiPlus size={16} /> New campaign
        </Button>
      </div>

      {showCreate && (
        <div className="mb-8">
          <CreateCampaignForm
            onCreated={(c) => {
              setShowCreate(false);
              navigate(`/campaigns/${c.id}`);
            }}
          />
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}

      {!error && campaigns === null && (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      )}

      {!error && campaigns !== null && campaigns.length === 0 && (
        <EmptyState title="No campaigns yet" description="Create your first campaign to start importing resumes." />
      )}

      {!error && campaigns !== null && campaigns.length > 0 && (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <Link key={c.id} to={`/campaigns/${c.id}`}>
              <Card className="flex items-center justify-between px-5 py-4 transition-colors hover:border-ink-faint">
                <div>
                  <p className="font-medium text-ink">{c.name}</p>
                  <p className="mt-0.5 text-xs text-ink-muted">{c.job_title}</p>
                </div>
                <div className="flex items-center gap-4">
                  <Badge color="var(--color-ink-muted)">{c.candidate_count} resumes</Badge>
                  <Badge color="#1FB37A">{c.shortlisted_count} shortlisted</Badge>
                  <FiArrowRight className="text-ink-faint" />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateCampaignForm({ onCreated }: { onCreated: (c: Campaign) => void }) {
  const [name, setName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = name.trim().length > 0 && jdFile !== null && !submitting;

  const submit = async () => {
    if (!canSubmit || !jdFile) return;
    setSubmitting(true);
    try {
      const campaign = await createCampaign({ name: name.trim(), jobTitle: jobTitle.trim() || undefined, jobDescriptionFile: jdFile });
      toast.success("Campaign created.");
      onCreated(campaign);
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Failed to create campaign.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="p-6">
      <h2 className="mb-4 text-sm font-semibold text-ink">Create campaign</h2>
      <div className="space-y-4">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-ink-muted">Campaign name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Backend Engineer Q3"
            className="w-full rounded-lg border border-base-border bg-base-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-signal"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-ink-muted">Job title (shown to candidates)</label>
          <input
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            placeholder="Defaults to campaign name if left blank"
            className="w-full rounded-lg border border-base-border bg-base-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-signal"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-ink-muted">Job description (.docx/.pdf)</label>
          <FileDropzone label="Upload job description" hint="Skills and experience requirements are extracted from this file" file={jdFile} onFileChange={setJdFile} />
        </div>
        <Button onClick={submit} disabled={!canSubmit}>
          {submitting ? "Creating..." : "Create campaign"}
        </Button>
      </div>
    </Card>
  );
}
