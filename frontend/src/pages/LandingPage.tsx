import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { FiArrowRight, FiBarChart2, FiFileText, FiZap } from "react-icons/fi";
import { Button, Card } from "@/components/ui/primitives";

const FEATURES = [
  {
    icon: FiFileText,
    title: "Structured extraction",
    description:
      "Parses the question paper and submission, splits sections, and matches each answer to its question.",
  },
  {
    icon: FiZap,
    title: "LLM-graded review",
    description:
      "Scores every answer across six dimensions and flags concrete, evidence-based issues.",
  },
  {
    icon: FiBarChart2,
    title: "Hiring-ready report",
    description:
      "One dashboard: overall score, breakdown by dimension, and a clear hiring recommendation.",
  },
];

export function LandingPage() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-20">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center"
      >
        <span className="inline-block rounded-full border border-base-border bg-base-surface px-3 py-1 text-xs text-ink-muted">
          AI-graded technical assessments
        </span>
        <h1 className="mx-auto mt-5 max-w-2xl text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          Review candidate assignments in minutes, not hours
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-ink-muted">
          Upload the question paper and a candidate's submission. Get a structured,
          explainable evaluation with a hiring recommendation you can defend.
        </p>
        <div className="mt-8">
          <Link to="/review">
            <Button size="lg">
              Start a review <FiArrowRight size={16} />
            </Button>
          </Link>
        </div>
      </motion.div>

      <div className="mt-20 grid gap-5 sm:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, description }, i) => (
          <motion.div
            key={title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 + i * 0.08 }}
          >
            <Card className="h-full p-6">
              <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg bg-signal/15 text-signal">
                <Icon size={16} />
              </div>
              <h3 className="text-sm font-semibold text-ink">{title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{description}</p>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
