import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { FiCheck, FiLoader } from "react-icons/fi";

const STEPS = [
  "Parsing documents",
  "Splitting sections",
  "Extracting questions",
  "Matching answers",
  "Evaluating candidate",
  "Building report",
];

// Purely cosmetic pacing — the backend call is a single request, so this
// just gives the wait some texture. It never blocks the real completion.
const STEP_INTERVAL_MS = 2200;

export function ProcessingSteps() {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveIndex((i) => Math.min(i + 1, STEPS.length - 1));
    }, STEP_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="mx-auto max-w-md">
      <div className="mb-8 text-center">
        <h2 className="text-lg font-semibold text-ink">Reviewing the submission</h2>
        <p className="mt-1 text-sm text-ink-muted">
          This runs a full LLM evaluation — it can take a minute or two.
        </p>
      </div>
      <ol className="space-y-1">
        {STEPS.map((step, i) => {
          const isDone = i < activeIndex;
          const isActive = i === activeIndex;
          return (
            <motion.li
              key={step}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5"
            >
              <span
                className={
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs " +
                  (isDone
                    ? "bg-grade-strong_hire/15 text-grade-strong_hire"
                    : isActive
                    ? "bg-signal/15 text-signal"
                    : "bg-base-surface2 text-ink-faint")
                }
              >
                {isDone ? (
                  <FiCheck size={13} />
                ) : isActive ? (
                  <FiLoader size={12} className="animate-spin" />
                ) : (
                  i + 1
                )}
              </span>
              <span
                className={
                  "text-sm " +
                  (isDone || isActive ? "text-ink" : "text-ink-faint")
                }
              >
                {step}
              </span>
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}
