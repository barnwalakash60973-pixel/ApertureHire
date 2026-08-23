import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import toast from "react-hot-toast";
import { FiCheck, FiDownload, FiExternalLink, FiRefreshCw, FiSave } from "react-icons/fi";
import { Badge, Button, Card, Skeleton } from "@/components/ui/primitives";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { AssignmentDocument } from "@/components/assignment/AssignmentDocument";
import {
  approveAssignment,
  downloadAssignment,
  editAssignment,
  generateAssignment,
  getAssignmentVersions,
  getCampaignAssignment,
  linkAssignment,
  regenerateAssignment,
  uploadAssignment,
  CampaignApiError,
} from "@/api/campaigns";
import type { Assignment, AssignmentVersion } from "@/types/campaign";

export function CampaignAssignmentPage() {
  const { campaignId } = useParams<{ campaignId: string }>();
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [loadingExisting, setLoadingExisting] = useState(true);
  const [versions, setVersions] = useState<AssignmentVersion[]>([]);
  const [mode, setMode] = useState<"generate" | "upload" | "link">("generate");

  // Generate form state
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [numQuestions, setNumQuestions] = useState(8);
  const [numSections, setNumSections] = useState(2);
  const [busy, setBusy] = useState(false);

  // Upload form state
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  // Google Drive link form state
  const [linkTitle, setLinkTitle] = useState("");
  const [driveLink, setDriveLink] = useState("");

  // Edit state
  const [editText, setEditText] = useState("");
  const [editing, setEditing] = useState(false);

  // Regenerate form state (shown once an assignment already exists, since
  // the brief/title inputs from the initial generate form aren't on screen
  // anymore but /regenerate still requires them)
  const [showRegenerateForm, setShowRegenerateForm] = useState(false);
  const [regenTitle, setRegenTitle] = useState("");
  const [regenBrief, setRegenBrief] = useState("");
  const [regenNumQuestions, setRegenNumQuestions] = useState(8);
  const [regenNumSections, setRegenNumSections] = useState(2);

  // Approve state
  const [deadlineDays, setDeadlineDays] = useState(7);

  const refreshVersions = (assignmentId: string) => {
    getAssignmentVersions(assignmentId).then(setVersions).catch(() => {});
  };

  useEffect(() => {
    if (!campaignId) return;
    getCampaignAssignment(campaignId)
      .then(setAssignment)
      .catch(() => setAssignment(null))
      .finally(() => setLoadingExisting(false));
  }, [campaignId]);

  useEffect(() => {
    if (assignment) {
      setEditText(assignment.current_version.question_paper_text);
      refreshVersions(assignment.id);
      setRegenTitle(assignment.title);
    }
  }, [assignment?.id, assignment?.version_count]);

  const doGenerate = async () => {
    if (!campaignId || !title.trim() || !brief.trim()) return;
    setBusy(true);
    try {
      const a = await generateAssignment(campaignId, { title: title.trim(), brief: brief.trim(), numQuestions, numSections });
      toast.success("Assignment generated.");
      setAssignment(a);
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  };

  const doUpload = async () => {
    if (!campaignId || !uploadTitle.trim() || !uploadFile) return;
    setBusy(true);
    try {
      const a = await uploadAssignment(campaignId, uploadTitle.trim(), uploadFile);
      toast.success("Assignment uploaded.");
      setAssignment(a);
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  const doDownload = async (format: "docx" | "pdf") => {
    if (!assignment) return;
    setBusy(true);
    try {
      await downloadAssignment(assignment.id, format);
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Download failed.");
    } finally {
      setBusy(false);
    }
  };

  const doLink = async () => {
    if (!campaignId || !linkTitle.trim() || !driveLink.trim()) return;
    setBusy(true);
    try {
      const a = await linkAssignment(campaignId, linkTitle.trim(), driveLink.trim());
      toast.success("Assignment linked.");
      setAssignment(a);
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Linking failed.");
    } finally {
      setBusy(false);
    }
  };

  const doRegenerate = async () => {
    if (!assignment || !regenBrief.trim()) {
      toast.error("Enter a brief to regenerate.");
      return;
    }
    setBusy(true);
    try {
      const a = await regenerateAssignment(assignment.id, {
        title: regenTitle.trim() || assignment.title,
        brief: regenBrief.trim(),
        numQuestions: regenNumQuestions,
        numSections: regenNumSections,
      });
      const isNewRound = a.id !== assignment.id;
      toast.success(isNewRound ? "Assignment was approved (locked) - created a new draft instead." : "Regenerated new version.");
      setAssignment(a);
      setShowRegenerateForm(false);
      setRegenBrief("");
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Regeneration failed.");
    } finally {
      setBusy(false);
    }
  };

  const doSaveEdit = async () => {
    if (!assignment) return;
    setBusy(true);
    try {
      const a = await editAssignment(assignment.id, editText);
      toast.success("Draft saved as new version.");
      setAssignment(a);
      setEditing(false);
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Edit failed - only draft assignments can be edited.");
    } finally {
      setBusy(false);
    }
  };

  const doApprove = async (versionId?: string) => {
    if (!assignment) return;
    setBusy(true);
    try {
      const result = await approveAssignment(assignment.id, deadlineDays, versionId);
      toast.success(`Approved v${result.approved_version_number} - ${result.candidates_notified} candidates notified.`);
      refreshVersions(assignment.id);
      setAssignment({ ...assignment, status: "approved" });
    } catch (err) {
      toast.error(err instanceof CampaignApiError ? err.message : "Approve failed.");
    } finally {
      setBusy(false);
    }
  };

  if (loadingExisting) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!assignment) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="mb-1 text-2xl font-semibold text-ink">Assignment</h1>
        <p className="mb-8 text-sm text-ink-muted">Generate one with AI, or upload your own.</p>

        <div className="mb-5 flex gap-2">
          <Button variant={mode === "generate" ? "primary" : "secondary"} size="sm" onClick={() => setMode("generate")}>
            Generate with AI
          </Button>
          <Button variant={mode === "upload" ? "primary" : "secondary"} size="sm" onClick={() => setMode("upload")}>
            Upload existing
          </Button>
          <Button variant={mode === "link" ? "primary" : "secondary"} size="sm" onClick={() => setMode("link")}>
            Google Drive link
          </Button>
        </div>

        {mode === "generate" ? (
          <Card className="space-y-4 p-6">
            <Field label="Title">
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. RAG Backend Assignment" className={inputCls} />
            </Field>
            <Field label="Brief - what should this test for?">
              <textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={3} placeholder="e.g. RAG + FastAPI backend, mid-level" className={inputCls} />
            </Field>
            <div className="flex gap-4">
              <Field label="Questions">
                <input type="number" min={1} max={30} value={numQuestions} onChange={(e) => setNumQuestions(Number(e.target.value))} className={inputCls} />
              </Field>
              <Field label="Sections">
                <input type="number" min={1} max={10} value={numSections} onChange={(e) => setNumSections(Number(e.target.value))} className={inputCls} />
              </Field>
            </div>
            <Button onClick={doGenerate} disabled={busy || !title.trim() || !brief.trim()}>
              {busy ? "Generating..." : "Generate assignment"}
            </Button>
          </Card>
        ) : mode === "upload" ? (
          <Card className="space-y-4 p-6">
            <Field label="Title">
              <input value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} placeholder="e.g. RAG Backend Assignment" className={inputCls} />
            </Field>
            <FileDropzone label="Upload assignment" hint=".docx/.pdf" file={uploadFile} onFileChange={setUploadFile} />
            <Button onClick={doUpload} disabled={busy || !uploadTitle.trim() || !uploadFile}>
              {busy ? "Uploading..." : "Upload assignment"}
            </Button>
          </Card>
        ) : (
          <Card className="space-y-4 p-6">
            <Field label="Title">
              <input value={linkTitle} onChange={(e) => setLinkTitle(e.target.value)} placeholder="e.g. RAG Backend Assignment" className={inputCls} />
            </Field>
            <Field label="Google Drive link">
              <input value={driveLink} onChange={(e) => setDriveLink(e.target.value)} placeholder="https://drive.google.com/..." className={inputCls} />
            </Field>
            <Button onClick={doLink} disabled={busy || !linkTitle.trim() || !driveLink.trim()}>
              {busy ? "Linking..." : "Link assignment"}
            </Button>
          </Card>
        )}
      </div>
    );
  }

  const isDraft = assignment.status === "draft";

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">{assignment.title}</h1>
          <p className="mt-1 text-xs text-ink-muted">
            v{assignment.current_version.version_number} of {assignment.version_count} - {assignment.current_version.label}
          </p>
        </div>
        <Badge color={isDraft ? "#D9A62E" : "#1FB37A"}>{isDraft ? "Draft" : "Approved (locked)"}</Badge>
      </div>

      <Card className="mb-5 p-5">
        {assignment.current_version.google_drive_link ? (
          <a href={assignment.current_version.google_drive_link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm text-signal hover:underline">
            <FiExternalLink size={14} /> {assignment.current_version.google_drive_link}
          </a>
        ) : editing ? (
          <textarea value={editText} onChange={(e) => setEditText(e.target.value)} rows={16} className={inputCls + " font-mono text-xs"} />
        ) : (
          <AssignmentDocument text={assignment.current_version.question_paper_text} />
        )}
      </Card>

      <div className="mb-8 flex flex-wrap gap-2">
        {isDraft && !editing && !assignment.current_version.google_drive_link && (
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>
            Edit
          </Button>
        )}
        {isDraft && editing && (
          <Button size="sm" onClick={doSaveEdit} disabled={busy}>
            <FiSave size={13} /> Save as new version
          </Button>
        )}
        <Button size="sm" variant="secondary" onClick={() => setShowRegenerateForm((v) => !v)} disabled={busy}>
          <FiRefreshCw size={13} /> Regenerate {!isDraft && "(new draft)"}
        </Button>
        {!assignment.current_version.google_drive_link && (
          <>
            <Button size="sm" variant="ghost" onClick={() => doDownload("docx")} disabled={busy}>
              <FiDownload size={13} /> Download .docx
            </Button>
            <Button size="sm" variant="ghost" onClick={() => doDownload("pdf")} disabled={busy}>
              <FiDownload size={13} /> Download PDF
            </Button>
          </>
        )}
      </div>

      {showRegenerateForm && (
        <Card className="mb-8 space-y-4 p-5">
          <Field label="Title">
            <input value={regenTitle} onChange={(e) => setRegenTitle(e.target.value)} className={inputCls} />
          </Field>
          <Field label="Brief - what should this test for?">
            <textarea value={regenBrief} onChange={(e) => setRegenBrief(e.target.value)} rows={3} placeholder="e.g. RAG + FastAPI backend, mid-level" className={inputCls} />
          </Field>
          <div className="flex gap-4">
            <Field label="Questions">
              <input type="number" min={1} max={30} value={regenNumQuestions} onChange={(e) => setRegenNumQuestions(Number(e.target.value))} className={inputCls} />
            </Field>
            <Field label="Sections">
              <input type="number" min={1} max={10} value={regenNumSections} onChange={(e) => setRegenNumSections(Number(e.target.value))} className={inputCls} />
            </Field>
          </div>
          <Button size="sm" onClick={doRegenerate} disabled={busy || !regenBrief.trim()}>
            {busy ? "Regenerating..." : "Confirm regenerate"}
          </Button>
        </Card>
      )}

      {isDraft && (
        <Card className="mb-8 flex items-end gap-3 p-5">
          <Field label="Deadline (days)">
            <input type="number" min={1} max={90} value={deadlineDays} onChange={(e) => setDeadlineDays(Number(e.target.value))} className={inputCls + " w-24"} />
          </Field>
          <Button onClick={() => doApprove()} disabled={busy}>
            <FiCheck size={14} /> Approve & send to candidates
          </Button>
        </Card>
      )}

      {versions.length > 1 && (
        <>
          <h2 className="mb-3 text-sm font-semibold text-ink">Version history</h2>
          <div className="space-y-2">
            {[...versions].reverse().map((v) => (
              <Card key={v.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm text-ink">
                    v{v.version_number} - {v.label}
                  </p>
                  <p className="text-xs text-ink-faint">{new Date(v.created_at).toLocaleString()}</p>
                </div>
                {v.is_approved ? (
                  <Badge color="#1FB37A">Currently approved</Badge>
                ) : (
                  <Button size="sm" variant="secondary" onClick={() => doApprove(v.id)} disabled={busy}>
                    Approve this version (rollback)
                  </Button>
                )}
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

const inputCls = "w-full rounded-lg border border-base-border bg-base-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-signal";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex-1">
      <label className="mb-1.5 block text-xs font-medium text-ink-muted">{label}</label>
      {children}
    </div>
  );
}
