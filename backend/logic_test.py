"""Targeted tests for the two logic changes that aren't covered by the
end-to-end flow: the proportional shortlist rule and ZIP extraction."""

import asyncio
import io
import os
import sys
import tempfile
import zipfile

os.environ["STORAGE_BACKEND"] = "local"

from app.services.review.resume_matcher import RuleBasedResumeMatcher  # noqa: E402
from app.utils.archive import extract_text_from_zip  # noqa: E402

failures = []


def check(label, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label} {'' if cond else extra}")
    if not cond:
        failures.append(label)


m = RuleBasedResumeMatcher()

print("\n[A] Proportional rule: same 1 missing skill, different JD sizes")

# Small JD: 3 required skills, candidate has 2. 1/3 missing = 33% > 20%.
small_jd = "Requires Python, Docker and Kubernetes."
small_resume = "Skills: Python, Docker"
small = m.match(small_jd, small_resume)

# Large JD: many required skills, candidate missing 1. Small share.
large_jd = "Requires Python, Docker, Kubernetes, FastAPI, PostgreSQL, Redis, AWS, Terraform, Kafka, React."
large_resume = "Skills: Python, Docker, Kubernetes, FastAPI, PostgreSQL, Redis, AWS, Terraform, Kafka"
large = m.match(large_jd, large_resume)

print(f"    small JD: required={len(small.required_skills)} missing={small.missing_skills} -> {small.decision.value}")
print(f"    large JD: required={len(large.required_skills)} missing={large.missing_skills} -> {large.decision.value}")

check("1-of-many missing is still shortlisted", large.decision.value == "shortlisted", large.decision_reason)
check("1-of-3 missing (33% gap) is NOT shortlisted", small.decision.value == "not_shortlisted", small.decision_reason)
check("the two now differ (old absolute rule treated them identically)",
      small.decision.value != large.decision.value)

print("\n[B] Experience is a hard gate")
exp_jd = "Requires Python and Docker. Requires 5+ years of experience."
exp_resume = "Skills: Python, Docker\n2 years of experience."
exp = m.match(exp_jd, exp_resume)
print(f"    perfect skills, short experience -> {exp.decision.value}")
check("perfect skill match still fails on unmet experience",
      exp.decision.value == "not_shortlisted", exp.decision_reason)

unknown_jd = "Requires Python and Docker. Requires 5+ years of experience."
unknown_resume = "Skills: Python, Docker"
unknown = m.match(unknown_jd, unknown_resume)
check("unparseable experience does NOT auto-fail the candidate",
      unknown.decision.value == "shortlisted", unknown.decision_reason)

print("\n[C] ZIP submission extraction")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("project/main.py", "def solve():\n    return 42\n")
    z.writestr("project/README.md", "# My Solution\nUses a hash map.\n")
    z.writestr("project/node_modules/junk/index.js", "SHOULD_NOT_APPEAR")
    z.writestr("project/.git/config", "SHOULD_NOT_APPEAR_EITHER")
    z.writestr("project/logo.png", b"\x89PNG\x00\x00binary")
    z.writestr("../escape.py", "TRAVERSAL_SHOULD_NOT_APPEAR")

zip_path = os.path.join(tempfile.gettempdir(), "sub.zip")
with open(zip_path, "wb") as f:
    f.write(buf.getvalue())

try:
    text = asyncio.run(extract_text_from_zip(zip_path))
    check("source file included", "def solve()" in text)
    check("markdown included", "Uses a hash map" in text)
    check("file path headers present", "FILE: project/main.py" in text)
    check("node_modules skipped", "SHOULD_NOT_APPEAR" not in text)
    check("path traversal entry skipped", "TRAVERSAL_SHOULD_NOT_APPEAR" not in text)
    check("binary image skipped", "PNG" not in text)
finally:
    os.remove(zip_path)

print("\n" + "=" * 60)
print("FAILURES:", failures if failures else "NONE - all checks passed")
print("=" * 60)

if failures:
    sys.exit(1)
