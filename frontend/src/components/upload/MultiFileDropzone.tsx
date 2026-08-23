import { useCallback, useRef, useState, type DragEvent } from "react";
import { FiFile, FiUploadCloud, FiX } from "react-icons/fi";
import { cx, formatBytes } from "@/lib/utils";

const ACCEPTED = [".pdf", ".docx"];
const MAX_SIZE = 15 * 1024 * 1024;

interface MultiFileDropzoneProps {
  label: string;
  hint: string;
  files: File[];
  onFilesChange: (files: File[]) => void;
}

export function MultiFileDropzone({ label, hint, files, onFilesChange }: MultiFileDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback(
    (candidates: FileList | null) => {
      if (!candidates) return;
      const valid: File[] = [];
      const rejected: string[] = [];
      Array.from(candidates).forEach((f) => {
        const ext = "." + f.name.split(".").pop()?.toLowerCase();
        if (!ACCEPTED.includes(ext)) {
          rejected.push(f.name);
          return;
        }
        if (f.size > MAX_SIZE) {
          rejected.push(f.name);
          return;
        }
        valid.push(f);
      });
      setError(rejected.length > 0 ? `Skipped ${rejected.length} file(s) - only .pdf/.docx under 15MB are accepted.` : null);
      if (valid.length > 0) onFilesChange([...files, ...valid]);
    },
    [files, onFilesChange]
  );

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const removeAt = (index: number) => {
    onFilesChange(files.filter((_, i) => i !== index));
  };

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
          isDragging ? "border-signal bg-signal/5" : "border-base-border bg-base-surface hover:border-ink-faint"
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
          multiple
          accept={ACCEPTED.join(",")}
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>
      {error && <p className="mt-2 text-xs text-grade-strong_no_hire">{error}</p>}

      {files.length > 0 && (
        <div className="mt-3 space-y-2">
          <p className="text-xs font-medium text-ink-muted">{files.length} file{files.length !== 1 ? "s" : ""} selected</p>
          <div className="max-h-56 space-y-1.5 overflow-y-auto">
            {files.map((f, i) => (
              <div key={`${f.name}-${i}`} className="flex items-center justify-between gap-3 rounded-lg border border-base-border bg-base-surface2 px-3 py-2">
                <div className="flex min-w-0 items-center gap-2.5">
                  <FiFile size={14} className="shrink-0 text-signal" />
                  <span className="truncate text-sm text-ink">{f.name}</span>
                  <span className="shrink-0 text-xs text-ink-faint">{formatBytes(f.size)}</span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeAt(i);
                  }}
                  aria-label={`Remove ${f.name}`}
                  className="shrink-0 rounded-md p-1 text-ink-faint transition-colors hover:bg-base-border/60 hover:text-ink"
                >
                  <FiX size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
