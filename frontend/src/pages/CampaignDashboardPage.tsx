import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FiArrowRight, FiAward, FiClock, FiFileText, FiUpload, FiUsers } from "react-icons/fi";
import { Badge, Card, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives";
import { getCampaign, getDashboard, getTimeline, CampaignApiError } from "@/api/campaigns";
import type { Campaign, CampaignDashboard, CampaignEvent } from "@/types/campaign";

const NEXT_ACTION_ROUTES: Record<string, string> = {
  "Import Resumes": "resumes",
  "Confirm Import": "resumes",
  "Approve Assignment": "assignment",
  "Waiting for Submissions": "evaluate",
  "Evaluate Assignments": "evaluate",
  "Approve & Send Results": "evaluate",
  "Review Final Results": "evaluate",
};

export function CampaignDashboardPage() {
  const { campaignId } = useParams<{ campaignId: string }>();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [dashboard, setDashboard] = useState<CampaignDashboard | null>(null);
  const [timeline, setTimeline] = useState<CampaignEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    if (!campaignId) return;
    setError(null);
    Promise.all([getCampaign(campaignId), getDashboard(campaignId), getTimeline(campaignId)])
      .then(([c, d, t]) => {
        setCampaign(c);
        setDashboard(d);
        setTimeline(t);
      })
      .catch((err: unknown) => setError(err instanceof CampaignApiError ? err.message : "Failed to load campaign."));
  };

  useEffect(load, [campaignId]);

  if (error) return <div className="mx-auto max-w-5xl px-6 py-10"><ErrorState message={error} onRetry={load} /></div>;

  if (!campaign || !dashboard) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 px-6 py-10">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  const nextActionPath = NEXT_ACTION_ROUTES[dashboard.next_action] ?? "resumes";

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">{campaign.name}</h1>
        <p className="mt-1 text-sm text-ink-muted">{campaign.job_title}</p>
      </div>

      {/* Guided-workflow banner - single source of truth is the backend's next_action field */}
      <Card className="mb-8 flex items-center justify-between border-signal/40 bg-signal/5 px-5 py-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-signal">Next action</p>
          <p className="mt-0.5 font-medium text-ink">{dashboard.next_action}</p>
        </div>
        <Link to={`/campaigns/${campaignId}/${nextActionPath}`}>
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-signal px-4 py-2 text-sm font-medium text-white hover:brightness-110">
            Go <FiArrowRight size={14} />
          </span>
        </Link>
      </Card>

      {/* Dashboard cards - pure DB counts, no LLM */}
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Resumes" value={dashboard.total_resumes} />
        <StatCard label="Shortlisted" value={dashboard.shortlisted_count} color="#1FB37A" />
        <StatCard label="Not Shortlisted" value={dashboard.not_shortlisted_count} color="#E27A3F" />
        <StatCard label="Assignment Sent" value={dashboard.assignment_sent_count} />
        <StatCard label="Submitted" value={dashboard.submitted_count} color="#5FBF6E" />
        <StatCard label="Overdue" value={dashboard.overdue_count} color="#E24E4E" />
        <StatCard label="Pending Approval" value={dashboard.pending_approval_count} color="#D9A62E" />
        <StatCard label="Final Selected" value={dashboard.final_selected_count} color="#1FB37A" />
        <StatCard label="Final Rejected" value={dashboard.final_rejected_count} color="#E24E4E" />
      </div>

      {dashboard.deadline && (
        <Card className="mb-8 flex items-center gap-3 px-5 py-3 text-sm text-ink-muted">
          <FiClock size={14} />
          <span>
            Deadline:{" "}
            {new Date(dashboard.deadline).toLocaleString("en-IN", {
              timeZone: "Asia/Kolkata",
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </span>
          {dashboard.days_remaining !== null && (
            <Badge color={dashboard.days_remaining < 0 ? "#E24E4E" : "#5FBF6E"}>
              {dashboard.days_remaining < 0 ? "Overdue" : `${dashboard.days_remaining} day(s) remaining`}
            </Badge>
          )}
        </Card>
      )}

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <NavCard to={`/campaigns/${campaignId}/resumes`} icon={<FiUsers size={16} />} label="Resumes & Candidates" />
        <NavCard to={`/campaigns/${campaignId}/assignment`} icon={<FiFileText size={16} />} label="Assignment" />
        <NavCard to={`/campaigns/${campaignId}/evaluate`} icon={<FiUpload size={16} />} label="Evaluate" />
        <NavCard to={`/campaigns/${campaignId}/selected`} icon={<FiAward size={16} />} label="Selected Candidates" />
      </div>

      <h2 className="mb-3 text-sm font-semibold text-ink">Timeline</h2>
      {timeline && timeline.length === 0 && <EmptyState title="No activity yet" description="Actions taken on this campaign will appear here." />}
      {timeline && timeline.length > 0 && (
        <Card className="divide-y divide-base-border">
          {timeline.map((e, i) => (
            <div key={i} className="flex items-center justify-between px-5 py-3">
              <p className="text-sm text-ink">{e.message}</p>
              <p className="shrink-0 text-xs text-ink-faint">
                {new Date(e.created_at).toLocaleString("en-IN", {                                          
                  timeZone: "Asia/Kolkata",
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </p>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <Card className="px-4 py-3">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold" style={color ? { color } : undefined}>
        {value}
      </p>
    </Card>
  );
}

function NavCard({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <Link to={to}>
      <Card className="flex items-center justify-between px-4 py-3.5 transition-colors hover:border-ink-faint">
        <span className="flex items-center gap-2.5 text-sm font-medium text-ink">
          {icon} {label}
        </span>
        <FiArrowRight size={14} className="text-ink-faint" />
      </Card>
    </Link>
  );
}
