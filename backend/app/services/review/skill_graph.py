"""
Builds a "skill graph" - a simple frequency profile of technologies/skills
mentioned across a candidate's answers. Pure Python + regex, no LLM call:
the evaluation LLM call already produced everything we need (the matched
Answer.text for every question), so this is a deterministic post-processing
step over data we already have.
"""

from __future__ import annotations

import re

from app.domain.models import SectionReport, SkillMention

# Curated keyword -> canonical display name. Order doesn't matter; matching
# is case-insensitive with word boundaries. Add to this list as needed -
# it's the only thing that needs updating to recognize a new skill.
_SKILL_KEYWORDS: dict[str, str] = {
    "python": "Python",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "azure": "Azure",
    "aws": "AWS",
    "gcp": "GCP",
    "rag": "RAG",
    "retrieval augmented generation": "RAG",
    "llm": "LLM",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "transformer": "Transformers",
    "embedding": "Embeddings",
    "vector database": "Vector DB",
    "vector db": "Vector DB",
    "pinecone": "Pinecone",
    "faiss": "FAISS",
    "chroma": "ChromaDB",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "kafka": "Kafka",
    "rabbitmq": "RabbitMQ",
    "graphql": "GraphQL",
    "rest api": "REST API",
    "restful": "REST API",
    "grpc": "gRPC",
    "microservice": "Microservices",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "jenkins": "Jenkins",
    "github actions": "GitHub Actions",
    "terraform": "Terraform",
    "react": "React",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "scikit-learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "celery": "Celery",
    "nginx": "Nginx",
    "oauth": "OAuth",
    "jwt": "JWT",
    "elasticsearch": "Elasticsearch",
    "prometheus": "Prometheus",
    "grafana": "Grafana",

    # -- Data Analyst -------------------------------------------------------
    "sql": "SQL",
    "tsql": "SQL",
    "pl/sql": "SQL",
    "kpi": "KPI Analysis",
    "kpis": "KPI Analysis",
    "dashboard": "Dashboarding",
    "dashboarding": "Dashboarding",
    "tableau": "Tableau",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "looker": "Looker",
    "excel": "Excel",
    "google sheets": "Google Sheets",
    "a/b testing": "A/B Testing",
    "ab testing": "A/B Testing",
    "data visualization": "Data Visualization",
    "etl": "ETL",
    "data warehouse": "Data Warehousing",
    "data warehousing": "Data Warehousing",
    "snowflake": "Snowflake",
    "bigquery": "BigQuery",
    "redshift": "Redshift",

    # -- Data Scientist -------------------------------------------------------
    "hypothesis testing": "Hypothesis Testing",
    "statistical analysis": "Statistical Analysis",
    "statistics": "Statistics",
    "regression": "Regression Modeling",
    "classification": "Classification Modeling",
    "clustering": "Clustering",
    "eda": "Exploratory Data Analysis",
    "exploratory data analysis": "Exploratory Data Analysis",
    "feature engineering": "Feature Engineering",
    "experiment design": "Experiment Design",
    "causal inference": "Causal Inference",
    "time series": "Time Series Analysis",
    "r programming": "R",
    "jupyter": "Jupyter",

    # -- ML Engineer / MLOps -------------------------------------------------
    "mlops": "MLOps",
    "model training": "Model Training",
    "training pipeline": "Training Pipelines",
    "training pipelines": "Training Pipelines",
    "model deployment": "Model Deployment",
    "model monitoring": "Model Monitoring",
    "data drift": "Data Drift Detection",
    "model drift": "Model Drift Detection",
    "mlflow": "MLflow",
    "kubeflow": "Kubeflow",
    "airflow": "Airflow",
    "feature store": "Feature Store",
    "model registry": "Model Registry",
    "a/b test model": "Model A/B Testing",
    "hyperparameter tuning": "Hyperparameter Tuning",
}

# Longer/multi-word keys must be matched before their substrings (e.g.
# "vector database" before "database" would matter if "database" were a
# key) - sort by keyword length descending so the regex alternation tries
# the more specific phrases first. Trailing "s?" tolerates simple plurals
# (embedding/embeddings, microservice/microservices, transformer/transformers)
# without needing a separate dictionary entry for each.
_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_SKILL_KEYWORDS, key=len, reverse=True)) + r")s?\b",
    re.IGNORECASE,
)

_MAX_SKILLS = 15
_BAR_CHAR = "\u2588"  # █
_BAR_MAX_LEN = 10


def build_skill_graph(section_reports: list[SectionReport]) -> list[SkillMention]:
    """Scan every answer's text for known skill keywords and return a
    mentions-sorted list, capped at _MAX_SKILLS, with a precomputed
    text-bar for simple display."""

    counts: dict[str, int] = {}
    for sr in section_reports:
        for qr in sr.question_reviews:
            text = qr.answer.text
            if not text:
                continue
            for canonical in extract_skill_set(text):
                counts[canonical] = counts.get(canonical, 0) + 1

    if not counts:
        return []

    max_count = max(counts.values())
    ranked = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)[:_MAX_SKILLS]

    return [
        SkillMention(
            skill=skill,
            mentions=count,
            bar=_BAR_CHAR * max(1, round((count / max_count) * _BAR_MAX_LEN)),
        )
        for skill, count in ranked
    ]


def extract_skill_set(text: str) -> set[str]:
    """Return the set of canonical skill names found anywhere in `text`,
    with no counts - used wherever we just need "which skills are present"
    rather than a frequency profile (e.g. the JD/resume matcher below).
    Shared keyword dictionary with build_skill_graph() so a skill added
    once is recognized everywhere."""

    return {_SKILL_KEYWORDS[m.group(1).lower()] for m in _PATTERN.finditer(text or "")}
