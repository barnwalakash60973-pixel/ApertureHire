"""Tests the HR Decision Layer (threshold / top_n / manual + override)
by stubbing the LLM review pipeline with deterministic scores. No API
key needed - the point under test is the SELECTION logic, not grading."""

import os
import shutil
import sys
import tempfile
import uuid

WORK = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{WORK}/t.db"
os.environ["LOCAL_STORAGE_DIR"] = f"{WORK}/storage"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["JWT_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.domain.enums import HiringRecommendation  # noqa: E402
from app.domain.models import FinalReport  # noqa: E402
import app.api.routes_campaigns as rc  # noqa: E402
from app.infrastructure.db.database import get_session_factory  # noqa: E402
from app.infrastructure.db.models import (  # noqa: E402
    AssignmentORM, AssignmentVersionORM, CampaignORM, CandidateORM, SubmissionORM,
)
from app.main import app  # noqa: E402

failures = []
SCORES = {}


def check(label, cond, extra=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label} {'' if cond else extra}")
    if not cond:
        failures.append(label)


class StubUseCase:
    """Returns a preset score per submission text - deterministic, 0 LLM."""

    async def execute_from_texts(self, question_paper_text: str, submission_text: str) -> FinalReport:
        score = SCORES[submission_text.strip()]
        return FinalReport(
            overall_score=score, section_reports=[], missing_topics=[], improvements=[],
            hiring_recommendation=list(HiringRecommendation)[0], hiring_rationale="stubbed",
        )


rc.get_review_use_case = lambda: StubUseCase()


async def seed(campaign_name, candidate_scores):
    """Create a campaign + approved assignment + submitted candidates."""
    sf = get_session_factory()
    async with sf() as s:
        c = CampaignORM(name=campaign_name, job_title="Engineer", job_description_text="Python. Docker.")
        s.add(c)
        await s.flush()
        a = AssignmentORM(campaign_id=c.id, title="A1", status="approved")
        s.add(a)
        await s.flush()
        v = AssignmentVersionORM(assignment_id=a.id, version_number=1,
                                 question_paper_text="Part A\nA.1 Question?", source="generated", label="Generated")
        s.add(v)
        await s.flush()
        a.approved_version_id = v.id

        ids = []
        for i, score in enumerate(candidate_scores):
            text = f"{campaign_name}-sub-{i}-{uuid.uuid4().hex[:6]}"
            SCORES[text] = score
            cand = CandidateORM(campaign_id=c.id, name=f"Cand{i}", email=f"c{i}@x.com",
                                resume_text="Python Docker", status="submitted")
            s.add(cand)
            await s.flush()
            s.add(SubmissionORM(candidate_id=cand.id, assignment_id=a.id, submission_text=text))
            ids.append(cand.id)
        await s.commit()
        return c.id, ids


async def statuses(ids):
    sf = get_session_factory()
    async with sf() as s:
        rows = (await s.execute(select(CandidateORM).where(CandidateORM.id.in_(ids)))).scalars().all()
        return {r.id: r.status for r in rows}


import anyio  # noqa: E402

with TestClient(app) as client:
    client.post("/api/v1/auth/register", json={"name": "HR", "email": "hr@x.com", "password": "password123"})
    tok = client.post("/api/v1/auth/login", json={"identifier": "hr@x.com", "password": "password123"}).json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}

    print("\n[A] Threshold mode, custom cutoff 7.5 (spec's example)")
    cid, ids = anyio.from_thread.run(seed, "thresh", [9.0, 8.0, 7.0, 5.0]) if False else client.portal.call(seed, "thresh", [9.0, 8.0, 7.0, 5.0])
    r = client.post(f"/api/v1/campaigns/{cid}/evaluations", headers=H,
                    json={"mode": "threshold", "score_threshold": 7.5})
    check("threshold eval 200", r.status_code == 200, r.text[:300])
    b = r.json()
    check("2 pending selection at >=7.5", b["pending_selected_count"] == 2, b)
    check("2 pending rejection below 7.5", b["pending_rejected_count"] == 2, b)

    r = client.post(f"/api/v1/campaigns/{cid}/evaluations/approve", headers=H)
    check("approve 200", r.status_code == 200, r.text[:300])
    b = r.json()
    check("2 selected at >=7.5", b["final_selected_count"] == 2, b)
    check("2 rejected below 7.5", b["final_rejected_count"] == 2, b)

    print("\n[B] Top-N mode (spec's 'Top 20' example, N=2 here)")
    cid2, ids2 = client.portal.call(seed, "topn", [9.0, 8.5, 8.0, 7.9])
    r = client.post(f"/api/v1/campaigns/{cid2}/evaluations", headers=H, json={"mode": "top_n", "top_n": 2})
    b = r.json()
    check("exactly N pending selected", b["pending_selected_count"] == 2, b)

    r = client.post(f"/api/v1/campaigns/{cid2}/evaluations/approve", headers=H)
    b = r.json()
    check("exactly N selected", b["final_selected_count"] == 2, b)
    st = client.portal.call(statuses, ids2)
    check("top scorers are the selected ones",
          st[ids2[0]] == "final_selected" and st[ids2[1]] == "final_selected"
          and st[ids2[3]] == "final_rejected", st)
    check("top_n fills seats even when whole pool is close/weak", b["final_rejected_count"] == 2, b)

    print("\n[C] Manual mode selects nobody automatically")
    cid3, ids3 = client.portal.call(seed, "manual", [9.0, 4.0])
    r = client.post(f"/api/v1/campaigns/{cid3}/evaluations", headers=H, json={"mode": "manual"})
    b = r.json()
    check("graded both", b["evaluated_count"] == 2, b)
    st = client.portal.call(statuses, ids3)
    check("left at 'evaluated' awaiting HR", all(v == "evaluated" for v in st.values()), st)

    print("\n[D] Manual override beats the automatic decision")
    # ids3[1] scored 4.0. Select them anyway.
    r = client.post(f"/api/v1/campaigns/{cid3}/candidates/{ids3[1]}/decision", headers=H,
                    json={"decision": "select", "reason": "Strong referral, weak on paper"})
    check("override 200", r.status_code == 200, r.text[:300])
    check("low scorer now selected", r.json()["status"] == "final_selected", r.json())
    check("marked as an actual change", r.json()["overridden"] is True)

    # Reject a high scorer from campaign A.
    r = client.post(f"/api/v1/campaigns/{cid}/candidates/{ids[0]}/decision", headers=H,
                    json={"decision": "reject", "reason": "Failed reference check"})
    check("high scorer can be rejected", r.json()["status"] == "final_rejected", r.json())

    print("\n[E] Re-confirming an existing decision does not re-notify")
    r = client.post(f"/api/v1/campaigns/{cid}/candidates/{ids[0]}/decision", headers=H,
                    json={"decision": "reject"})
    check("no-op override reports overridden=False", r.json()["overridden"] is False, r.json())

    print("\n[F] Overrides are on the audit timeline")
    tl = client.get(f"/api/v1/campaigns/{cid3}/timeline", headers=H).json()
    ovr = [e for e in tl if e["event_type"] == "manual_override"]
    check("override logged", len(ovr) == 1, tl)
    check("reason captured in the log", "Strong referral" in ovr[0]["message"], ovr)

    print("\n[G] Rescuing a rejected candidate clears their retention clock")
    sf_ids = [ids[0]]

    async def get_deadline(cand_id):
        sf = get_session_factory()
        async with sf() as s:
            return (await s.get(CandidateORM, cand_id)).retention_deadline

    d_before = client.portal.call(get_deadline, ids[0])
    check("rejected candidate has a retention deadline", d_before is not None)
    client.portal.call(lambda: None) if False else None
    r = client.post(f"/api/v1/campaigns/{cid}/candidates/{ids[0]}/decision", headers=H, json={"decision": "select"})
    d_after = client.portal.call(get_deadline, ids[0])
    check("rescued candidate's retention clock cleared", d_after is None, d_after)

    print("\n[H] Reports persisted for ALL graded candidates (needed for re-ranking)")

    async def report_count(campaign_id):
        sf = get_session_factory()
        async with sf() as s:
            cands = (await s.execute(select(CandidateORM).where(CandidateORM.campaign_id == campaign_id))).scalars().all()
            n = 0
            for c in cands:
                sub = (await s.execute(select(SubmissionORM).where(SubmissionORM.candidate_id == c.id))).scalars().first()
                if sub and sub.report is not None:
                    n += 1
            return n

    check("rejected candidates keep their report until retention purge",
          client.portal.call(report_count, cid2) == 4, client.portal.call(report_count, cid2))

print("\n" + "=" * 60)
print("FAILURES:", failures if failures else "NONE - all checks passed")
print("=" * 60)
shutil.rmtree(WORK, ignore_errors=True)

if failures:
    sys.exit(1)
