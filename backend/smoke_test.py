"""End-to-end smoke test of the NEW paths: public apply -> storage ->
confirm (rejection email + retention) -> download -> purge. Uses
FastAPI's TestClient against a throwaway sqlite DB. No LLM calls: the
only LLM step (evaluation) is not exercised here."""

import os
import shutil
import sys
import tempfile

WORK = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{WORK}/test.db"
os.environ["LOCAL_STORAGE_DIR"] = f"{WORK}/storage"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["JWT_SECRET_KEY"] = "test-secret-for-smoke-test"

from fastapi.testclient import TestClient  # noqa: E402
from docx import Document  # noqa: E402

from app.main import app  # noqa: E402


def make_docx(path: str, text: str) -> bytes:
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(path)
    with open(path, "rb") as f:
        return f.read()


JD = """Senior Python Engineer
We need strong Python, FastAPI, Docker, PostgreSQL and AWS skills.
Requires 3+ years of experience."""

GOOD_RESUME = """Asha Verma
asha.verma@example.com
5 years of experience building backend systems.
Skills: Python, FastAPI, Docker, PostgreSQL, AWS, Redis"""

WEAK_RESUME = """Rahul Singh
rahul.singh@example.com
1 years of experience.
Skills: HTML, CSS"""

failures = []


def check(label, cond, extra=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} {extra}")
        failures.append(label)


with TestClient(app) as client:
    print("\n[1] HR register + login")
    r = client.post("/api/v1/auth/register", json={
        "name": "HR One", "email": "hr@corp.com", "mobile_number": "9999999999", "password": "password123",
    })
    check("register", r.status_code in (200, 201), r.text[:200])
    r = client.post("/api/v1/auth/login", json={"identifier": "hr@corp.com", "password": "password123"})
    check("login", r.status_code == 200, r.text[:200])
    token = r.json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    print("\n[2] Create campaign (JD via docx upload)")
    jd_bytes = make_docx(f"{WORK}/jd.docx", JD)
    r = client.post("/api/v1/campaigns", headers=H,
                    data={"name": "Backend Hiring 2026", "job_title": "Senior Python Engineer"},
                    files={"job_description_file": ("jd.docx", jd_bytes,
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    check("create campaign", r.status_code == 200, r.text[:300])
    cid = r.json()["id"]

    print("\n[3] PUBLIC job page (no auth)")
    r = client.get(f"/api/v1/public/campaigns/{cid}")
    check("public campaign visible unauthenticated", r.status_code == 200, r.text[:200])
    check("public payload has no internal counts", "candidate_count" not in r.json())

    print("\n[4] PUBLIC apply x2 (no auth) - strong + weak candidate")
    good_bytes = make_docx(f"{WORK}/good.docx", GOOD_RESUME)
    weak_bytes = make_docx(f"{WORK}/weak.docx", WEAK_RESUME)

    form_good = {
        "full_name": "Asha Verma", "email": "asha.verma@example.com", "phone_number": "9876543210",
        "degree": "B.Tech CSE", "cgpa": "8.9", "college": "IIIT Lucknow", "graduation_year": "2021",
        "skills": "Python, FastAPI", "github_url": "https://github.com/asha",
    }
    r = client.post(f"/api/v1/public/campaigns/{cid}/apply", data=form_good,
                    files={"resume": ("good.docx", good_bytes,
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    check("strong candidate apply", r.status_code == 200, r.text[:300])
    good_id = r.json()["candidate_id"]

    form_weak = {
        "full_name": "Rahul Singh", "email": "rahul.singh@example.com", "phone_number": "9876500000",
        "degree": "BCA", "cgpa": "6.5", "college": "Some College", "graduation_year": "2025",
    }
    r = client.post(f"/api/v1/public/campaigns/{cid}/apply", data=form_weak,
                    files={"resume": ("weak.docx", weak_bytes,
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    check("weak candidate apply", r.status_code == 200, r.text[:300])
    weak_id = r.json()["candidate_id"]

    print("\n[5] Duplicate-email guard")
    r = client.post(f"/api/v1/public/campaigns/{cid}/apply", data=form_good,
                    files={"resume": ("good.docx", good_bytes,
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    check("duplicate rejected with 409", r.status_code == 409, f"got {r.status_code}")

    print("\n[6] Bad file type rejected")
    r = client.post(f"/api/v1/public/campaigns/{cid}/apply",
                    data={**form_weak, "email": "other@example.com"},
                    files={"resume": ("x.exe", b"MZ\x00\x00", "application/octet-stream")})
    check("exe rejected with 415", r.status_code == 415, f"got {r.status_code}")

    print("\n[7] Structured fields persisted (were missing entirely before)")
    r = client.get(f"/api/v1/campaigns/{cid}/candidates", headers=H)
    check("list candidates", r.status_code == 200, r.text[:200])
    cands = {c["id"]: c for c in r.json()}
    g = cands[good_id]
    check("cgpa stored", g["cgpa"] == "8.9", g.get("cgpa"))
    check("college stored", g["college"] == "IIIT Lucknow", g.get("college"))
    check("graduation_year stored", g["graduation_year"] == 2021, g.get("graduation_year"))
    check("phone stored", g["phone"] == "9876543210", g.get("phone"))
    check("name is typed not regex-guessed", g["name"] == "Asha Verma", g.get("name"))
    check("resume_available true", g["resume_available"] is True)

    print("\n[8] Rule-based screening decisions")
    check("strong candidate shortlisted", g["match_result"]["decision"] == "shortlisted",
          g["match_result"]["decision_reason"])
    check("weak candidate not shortlisted", cands[weak_id]["match_result"]["decision"] == "not_shortlisted",
          cands[weak_id]["match_result"]["decision_reason"])

    print("\n[9] Resume file actually downloadable (was discarded before)")
    r = client.get(f"/api/v1/campaigns/{cid}/candidates/{good_id}/resume", headers=H)
    check("resume download 200", r.status_code == 200, f"got {r.status_code}")
    check("resume bytes match uploaded", r.content == good_bytes, f"{len(r.content)} vs {len(good_bytes)}")
    check("download requires auth", client.get(f"/api/v1/campaigns/{cid}/candidates/{good_id}/resume").status_code in (401, 403))

    print("\n[10] Confirm import -> shortlist + rejection emails, retention clock set")
    r = client.post(f"/api/v1/campaigns/{cid}/resumes/confirm", headers=H)
    check("confirm 200", r.status_code == 200, r.text[:300])
    body = r.json()
    check("1 shortlisted", body["shortlisted_count"] == 1, body)
    check("1 not shortlisted", body["not_shortlisted_count"] == 1, body)

    print("\n[11] HR manual purge of rejected (retention)")
    r = client.post(f"/api/v1/campaigns/{cid}/purge-rejected", headers=H)
    check("purge 200", r.status_code == 200, r.text[:200])
    check("purged 1 rejected candidate", r.json()["purged_count"] == 1, r.json())

    r = client.get(f"/api/v1/campaigns/{cid}/candidates/{weak_id}/resume", headers=H)
    check("purged resume now gone (410)", r.status_code == 410, f"got {r.status_code}")

    r = client.get(f"/api/v1/campaigns/{cid}/candidates", headers=H)
    still = {c["id"]: c for c in r.json()}
    check("purged candidate row KEPT for audit", weak_id in still)
    check("shortlisted candidate resume untouched",
          client.get(f"/api/v1/campaigns/{cid}/candidates/{good_id}/resume", headers=H).status_code == 200)

    print("\n[12] Archive closes public applications")
    r = client.post(f"/api/v1/campaigns/{cid}/archive", headers=H)
    check("archive 200", r.status_code == 200, r.text[:200])
    r = client.post(f"/api/v1/public/campaigns/{cid}/apply",
                    data={**form_weak, "email": "late@example.com"},
                    files={"resume": ("weak.docx", weak_bytes,
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    check("closed campaign rejects new applicants (410)", r.status_code == 410, f"got {r.status_code}")

print("\n" + "=" * 60)
print("FAILURES:", failures if failures else "NONE - all checks passed")
print("=" * 60)
shutil.rmtree(WORK, ignore_errors=True)

if failures:
    sys.exit(1)
