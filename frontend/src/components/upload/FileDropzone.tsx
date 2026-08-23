import { useCallback, useRef, useState, type DragEvent } from "react";
import { FiFile, FiUploadCloud, FiX } from "react-icons/fi";
import { cx, formatBytes } from "@/lib/utils";

const DEFAULT_ACCEPTED = [".pdf", ".docx"];

interface FileDropzoneProps {
  label: string;
  hint: string;
  file: File | null;
  onFileChange: (file: File | null) => void;
  accept?: string[];
}

export function FileDropzone({ label, hint, file, onFileChange, accept = DEFAULT_ACCEPTED }: FileDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndSet = useCallback(
    (candidate: File | undefined) => {
      if (!candidate) return;
      const ext = "." + candidate.name.split(".").pop()?.toLowerCase();
      if (!accept.includes(ext)) {
        setError(`Unsupported file type "${ext}". Use ${accept.join(" or ")}.`);
        return;
      }
      if (candidate.size > 15 * 1024 * 1024) {
        setError("File exceeds the 15MB limit.");
        return;
      }
      setError(null);
      onFileChange(candidate);
    },
    [onFileChange, accept]
  );

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    validateAndSet(e.dataTransfer.files?.[0]);
  };

  if (file) {
    return (
      <div className="rounded-xl2 border border-base-border bg-base-surface2 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-signal/15 text-signal">
              <FiFile size={16} />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink">{file.name}</p>
              <p className="text-xs text-ink-muted">{formatBytes(file.size)}</p>
            </div>
          </div>
          <button
            onClick={() => onFileChange(null)}
            aria-label={`Remove ${file.name}`}
            className="shrink-0 rounded-md p-1.5 text-ink-faint transition-colors hover:bg-base-border/60 hover:text-ink"
          >
            <FiX size={15} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        className={cx(
          "flex cursor-pointer flex-col items-center justify-center gap-2.5 rounded-xl2 border-2 border-dashed px-6 py-10 text-center transition-colors",
          isDragging
            ? "border-signal bg-signal/5"
            : "border-base-border bg-base-surface hover:border-ink-faint"
        )}
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-base-surface2 text-ink-muted">
          <FiUploadCloud size={18} />
        </div>
        <div>
          <p className="text-sm font-medium text-ink">{label}</p>
          <p className="mt-0.5 text-xs text-ink-muted">{hint}</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={accept.join(",")}
          className="hidden"
          onChange={(e) => validateAndSet(e.target.files?.[0])}
        />
      </div>
      {error && <p className="mt-2 text-xs text-grade-strong_no_hire">{error}</p>}
    </div>
  );
}
