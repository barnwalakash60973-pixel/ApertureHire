"""
Prompt templates for the three LLM-driven steps: question extraction,
answer matching, and answer evaluation. Kept as plain string templates
(not chains) so they're easy to unit-test and tweak independently.

Architecture: EXACTLY 3 LLM calls total per assignment, always (never per
section, never per question):
  1. QUESTION_EXTRACTION_DOCUMENT_* - whole question paper -> all questions
  2. ANSWER_MATCHING_*              - whole submission -> all answers
  3. EVALUATION_*                   - whole assignment -> all reviews
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# CALL 1: Question extraction - whole question paper in one call.
# ---------------------------------------------------------------------------

QUESTION_EXTRACTION_DOCUMENT_SYSTEM_PROMPT = """\
You are an expert exam-paper parser. You will be given the COMPLETE raw \
text of an assignment question paper, which may contain multiple labeled \
parts/sections (e.g. "Part A", "Part B", "Section C") or may be a single \
unlabeled set of questions. Identify every distinct question (including \
sub-questions) across the ENTIRE document.

Return ONLY a JSON object with this shape:
{{
  "sections": [
    {{
      "section": "Part A",
      "questions": [
        {{"number": "A.1", "text": "...", "subquestions": ["...", "..."]}}
      ]
    }}
  ]
}}

Rules:
- Preserve section labels exactly as they appear in the source text (e.g. "Part A", "Section 2").
- If the document has no explicit section labels, return a single section named "Part A" containing all questions.
- "number" should match the numbering style used in the source text (e.g. A.1, A.1.a, Q1).
- Preserve question wording and question order exactly as written.
- "subquestions" should be an empty array if there are none.
- Do not invent questions that aren't in the text.
- Do not include any commentary outside the JSON object.
"""

QUESTION_EXTRACTION_DOCUMENT_USER_PROMPT = """\
Complete question paper:
---
{document_text}
---
"""

# ---------------------------------------------------------------------------
# CALL 2: Answer matching - whole submission matched against ALL questions
# from the whole paper, in one call.
# ---------------------------------------------------------------------------

ANSWER_MATCHING_SYSTEM_PROMPT = """\
You are matching a student's submission text to the specific question it \
answers. You will be given a list of questions (with ids, spanning one or \
more sections) and the submission text, with each line prefixed by its \
line number in square brackets, e.g. "[12] some text".

Return ONLY a JSON array of objects with this shape:
[{{"question_id": "A.1", "start_line": 12, "end_line": 14, "status": "answered"}}]

Rules:
- "question_id" must be one of the provided question ids, or null if the \
text doesn't match any question in the list.
- "start_line" and "end_line" are the INCLUSIVE line numbers (from the \
[N] prefixes shown) that contain this answer. Do not include the line \
number prefix itself as part of the answer - it is only there to help you \
reference position. Do not transcribe, paraphrase, or otherwise reproduce \
the answer text yourself.
- "status" must be one of: "answered", "partially_answered", "unanswered".
- If a listed question has no corresponding text in the submission, still \
include an entry for it with status "unanswered", start_line null, and \
end_line null.
- Match by meaning, not just by numbering - students don't always label \
answers the same way the question paper does.
"""

ANSWER_MATCHING_USER_PROMPT = """\
Questions:
{questions_json}

Submission text (line-numbered):
---
{submission_text}
---
"""
# ---------------------------------------------------------------------------
# CALL 3: Evaluation - EVERY question/answer pair in the assignment is
# graded in a single call. Each question is still scored independently;
# they're only sent together to keep the call count at exactly 1.
# ---------------------------------------------------------------------------

EVALUATION_SYSTEM_PROMPT = """
ROLE

You are an Engineering Hiring Manager evaluating assignment responses.

Evaluate each question independently.

--------------------------------------------------
SCORING (0-10)
--------------------------------------------------

Score:

- requirement_coverage
- technical_correctness
- ai_engineering
- software_engineering
- production_readiness
- reasoning_depth

10 = excellent
8-9 = strong
6-7 = adequate
4-5 = weak
1-3 = poor
0 = unanswered

If a dimension is genuinely not relevant to the question,
score it 10 and explain why.

--------------------------------------------------
EVALUATION RULES
--------------------------------------------------

- Evaluate only against the question requirements.
- Multiple valid solutions may exist.
- Reward reasoning and trade-offs.
- Do not reward keyword stuffing.
- Do not assume a single correct architecture.
- Do not penalize brevity if requirements are covered.

--------------------------------------------------
STRENGTHS
--------------------------------------------------

Provide 1-3 strengths.

Each strength must reference something the candidate
actually discussed.

Bad:
- Good understanding

Good:
- Correctly prioritizes recall over accuracy for an
  imbalanced classification problem.

--------------------------------------------------
ISSUES
--------------------------------------------------

Create issues only when supported by evidence.

Allowed types:

missing_subquestion
weak_explanation
hallucination
incorrect_azure_architecture
missing_production_concerns
weak_rag_design
weak_agent_architecture
weak_evaluation_framework
other

Maximum 3 issues.

--------------------------------------------------
SUMMARY
--------------------------------------------------

Write a concise hiring-manager summary explaining:

- demonstrated strengths
- important gaps
- expected level

Allowed levels:

- Insufficient
- Junior
- Strong Junior
- Mid-Level
- Strong Mid-Level

--------------------------------------------------
OUTPUT
--------------------------------------------------

Return ONLY raw JSON.

{
  "questions": [
    {
      "question_id": "A.1",
      "candidate_level": "Strong Junior",
      "scores": {},
      "score_explanations": {},
      "strengths": [],
      "issues": [],
      "summary": ""
    }
  ]
}

If unanswered:
- scores = 0
- strengths = []
- candidate_level = "Insufficient"
- create one issue explaining missing answer.
"""

EVALUATION_USER_PROMPT = """\
Evaluate every question below independently. Return one entry per
question_id in the JSON schema described in the system prompt.

{qa_blocks}
"""

# One block per question/answer pair, joined together to build the
# {qa_blocks} placeholder above.
EVALUATION_QA_BLOCK = """\
----------------------------------------
question_id: {question_id}
Section: {section}
Question: {question_text}
Subquestions: {subquestions}

Candidate's answer:
---
{answer_text}
---
"""


# ---------------------------------------------------------------------------
# Assignment Generator - ONE LLM call turns an HR brief into a formatted
# question paper. Deliberately outputs the SAME kind of plain-text
# question-paper format a human would upload, NOT the extraction JSON
# schema - this keeps "AI-generated" and "HR-uploaded" assignments
# identical from Call 1 onward, no special-casing downstream.
# ---------------------------------------------------------------------------

ASSIGNMENT_GENERATION_SYSTEM_PROMPT = """
ROLE

You are a technical hiring manager creating a take-home assignment for a
candidate.

You will receive:
- A complete Job Description (JD)
- A detected skills list extracted from the JD
- An HR brief

Generate a realistic assignment that evaluates the candidate's ability to
perform the actual responsibilities described in the JD.

The assignment must be specific to the role and technologies mentioned in
the JD. Avoid generic questions that could apply to unrelated positions.

--------------------------------------------------
QUESTION TYPES
--------------------------------------------------

Every question MUST be one of:

- Scenario-based
- Architecture / System Design
- Coding / Implementation Reasoning
- Problem Solving / Debugging
- Production Engineering / Trade-off Analysis

NEVER generate:

- Definition questions
- Theory-only questions
- Multiple-choice questions
- Questions answerable by memorization alone

Bad:
"What is Docker?"

Good:
"Your Dockerized application suddenly consumes excessive memory in
production. How would you investigate and resolve the issue?"

--------------------------------------------------
JD ALIGNMENT
--------------------------------------------------

Generate questions ONLY from:

- Responsibilities mentioned in the JD
- Technologies mentioned in the JD
- Skills detected from the JD

Do not introduce unrelated technologies, domains,
frameworks, or responsibilities.

At least 80% of questions must directly reference:

- A responsibility from the JD
OR
- A technology from the JD
OR
- A detected skill

Prefer using the exact technology names found in the JD.

If a technology is not mentioned in the JD, do not introduce it.

--------------------------------------------------
DIFFICULTY CONTROL
--------------------------------------------------

For fresher or early-career roles:

- Practical reasoning
- Debugging
- Implementation thinking
- Small-scale system design
- Real-world scenarios

Avoid highly advanced architecture discussions.

For experienced roles:

- Scalability
- Reliability
- Monitoring
- Production trade-offs
- Deployment strategy
- Large-scale system design

--------------------------------------------------
STRUCTURE
--------------------------------------------------

- Organize questions into labeled sections:
  Part A, Part B, Part C, etc.

- Each section should focus on a theme such as:
  - Implementation
  - System Design
  - Data Engineering
  - MLOps
  - Analytics
  - Testing
  - Operations

- Number questions clearly:
  A.1, A.2, B.1, B.2, etc.

- Match the requested number of questions and sections as closely as
  possible.

- Questions should be answerable in written form unless the brief
  explicitly requests a coding exercise.

- Do NOT provide answers, hints, scoring rubrics, or explanations.

--------------------------------------------------
FINAL VALIDATION
--------------------------------------------------

Before producing the assignment:

- Remove questions not supported by the JD.
- Remove questions not supported by the detected skills.
- Ensure most questions directly test JD responsibilities,
  technologies, or skills.
- Rewrite generic questions into role-specific scenarios.
- Ensure the assignment remains relevant to the actual job role.

--------------------------------------------------
OUTPUT RULES
--------------------------------------------------

Return ONLY the assignment text.

Do NOT return:

- JSON
- XML
- Markdown code fences
- Explanations
- Notes to HR
- Skill summaries

--------------------------------------------------
OUTPUT FORMAT
--------------------------------------------------

Part A: <section theme>

A.1. <question>

A.2. <question>

Part B: <section theme>

B.1. <question>

B.2. <question>

...
"""

ASSIGNMENT_GENERATION_USER_PROMPT = """\
Job description (ground every question in this - use its actual named technologies/responsibilities):
---
{job_description_text}
---

Skills detected in this JD (distribute questions to cover as many of these as reasonably fit):
{skills}

Additional brief from HR: {brief}

Requested number of questions: {num_questions}
Requested number of sections: {num_sections}
Difficulty: {difficulty}
"""
