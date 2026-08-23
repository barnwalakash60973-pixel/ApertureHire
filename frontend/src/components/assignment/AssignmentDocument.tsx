/**
 * Renders the plain-text question paper (see
 * ASSIGNMENT_GENERATION_SYSTEM_PROMPT's OUTPUT FORMAT - "Part A: <theme>",
 * blank line, "A.1. <question>", ...) as a formatted document instead of
 * a raw monospace dump, so HR sees roughly what the candidate will see.
 */

type Block =
  | { type: "heading"; text: string }
  | { type: "question"; number: string; text: string }
  | { type: "paragraph"; text: string };

const HEADING_RE = /^part\s+[a-z0-9]+\s*[:.-]/i;
const QUESTION_RE = /^((?:[a-z]+\.)?\d+(?:\.\d+)*\.)\s+(\S.*)$/i;

function parseAssignmentText(raw: string): Block[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => {
      if (HEADING_RE.test(line)) return { type: "heading", text: line } as const;
      const match = line.match(QUESTION_RE);
      if (match) return { type: "question", number: match[1], text: match[2] } as const;
      return { type: "paragraph", text: line } as const;
    });
}

export function AssignmentDocument({ text }: { text: string }) {
  const blocks = parseAssignmentText(text);

  if (blocks.length === 0) {
    return <p className="text-sm text-ink-faint">No content yet.</p>;
  }

  return (
    <div className="rounded-lg bg-base-surface2 px-8 py-7 text-ink shadow-sm ring-1 ring-base-border">
      {blocks.map((block, i) => {
        if (block.type === "heading") {
          return (
            <h2 key={i} className="mt-6 mb-3 text-sm font-bold uppercase tracking-wide text-signal first:mt-0">
              {block.text}
            </h2>
          );
        }
        if (block.type === "question") {
          return (
            <p key={i} className="mb-4 text-[13.5px] leading-relaxed text-ink">
              <span className="mr-1.5 font-semibold text-ink">{block.number}</span>
              {block.text}
            </p>
          );
        }
        return (
          <p key={i} className="mb-4 text-[13.5px] leading-relaxed text-ink-muted">
            {block.text}
          </p>
        );
      })}
    </div>
  );
}
