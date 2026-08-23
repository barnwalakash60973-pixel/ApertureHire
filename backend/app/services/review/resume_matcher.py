"""
Rule-based (NO LLM) JD <-> resume matcher, per the bulk-screening diagram:
  - 100% skill match, and experience requirement met (or not stated) -> shortlisted
  - Missing a small share of required skills (see _MAX_MISSING_SKILL_RATIO) -> still shortlisted
  - Missing more than that share, OR failing the experience requirement -> not_shortlisted

This is a SCREENING outcome, not a final hiring decision - that's why it's
"shortlisted"/"not_shortlisted" rather than "selected"/"rejected".

Pure regex/dictionary comparison, safe to run at any scale (100 to
100,000 resumes) since it makes zero network/LLM calls.

FIXED (was an absolute "missing <=1 skill" threshold): that treated
missing 1-of-3 required skills (33% gap) the same as missing 1-of-15
(6.7% gap) - a JD listing many required skills was effectively much more
forgiving than one listing few. The tolerance is now floor(ratio x
required_count), which has the deliberate property that a SHORT skill
list gets ZERO tolerance: if a JD names only 3 skills, all 3 are
plausibly core and missing one is meaningful, whereas one miss out of 15
is noise. Verify this matches your actual JDs before trusting it - it is
a defensible default, not a calibrated one, and the right ratio depends
on how your recruiters write requirement lists.

Experience is evaluated as a separate, non-negotiable gate: not stated
or unparseable -> ignored (can't fail on an unknown); stated and unmet
-> not_shortlisted regardless of skill match, since a hard "3+ years
required" is usually non-negotiable in practice, whereas "knows GraphQL
vs REST" often isn't.
"""

from __future__ import annotations

import math

from app.core.logging import get_logger
from app.domain.enums import MatchDecision
from app.domain.models import ResumeMatchResult
from app.services.review.experience_extractor import extract_candidate_years, extract_required_years
from app.services.review.resume_profile_extractor import extract_resume_profile
from app.services.review.skill_graph import extract_skill_set

logger = get_logger(__name__)

# A candidate may be missing up to this SHARE of the JD's required skills
# and still be shortlisted, rounded DOWN. No floor of 1 on purpose - see
# the module docstring: short requirement lists get zero tolerance.
_MAX_MISSING_SKILL_RATIO = 0.2


class RuleBasedResumeMatcher:
    """Deterministic JD<->resume comparator. No LLM, no network call -
    same class works whether you call it once or 100,000 times."""

    def match(self, jd_text: str, resume_text: str) -> ResumeMatchResult:
        required_skills = extract_skill_set(jd_text)
        resume_skills = extract_skill_set(resume_text)

        matched_skills = sorted(required_skills & resume_skills)
        missing_skills = sorted(required_skills - resume_skills)

        jd_min_years = extract_required_years(jd_text)
        candidate_years = extract_candidate_years(resume_text)

        experience_satisfied: bool | None
        if jd_min_years is None:
            experience_satisfied = None  # JD didn't state a requirement - nothing to fail
        elif candidate_years is None:
            experience_satisfied = None  # Couldn't determine - don't penalize on an unknown
        else:
            experience_satisfied = candidate_years >= jd_min_years

        max_missing_skills = math.floor(len(required_skills) * _MAX_MISSING_SKILL_RATIO)
        skills_ok = len(missing_skills) <= max_missing_skills
        # Experience is a hard gate, not blendable with the skill ratio -
        # see module docstring for why.
        decision = (
            MatchDecision.SHORTLISTED
            if skills_ok and experience_satisfied is not False
            else MatchDecision.NOT_SHORTLISTED
        )

        reason = self._build_reason(
            decision, missing_skills, jd_min_years, candidate_years, experience_satisfied
        )

        profile = extract_resume_profile(resume_text)

        result = ResumeMatchResult(
            match_score=self._compute_score(required_skills, matched_skills, experience_satisfied),
            education=profile["education"],
            projects=profile["projects"],
            certifications=profile["certifications"],
            experience_entries=profile["experience_entries"],
            required_skills=sorted(required_skills),
            resume_skills=sorted(resume_skills),
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            jd_min_years_experience=jd_min_years,
            candidate_years_experience=candidate_years,
            experience_satisfied=experience_satisfied,
            decision=decision,
            decision_reason=reason,
        )
        logger.info(
            "Resume matched (rule-based, 0 LLM calls): decision=%s, score=%.1f, missing_skills=%d, experience_satisfied=%s",
            decision.value, result.match_score, len(missing_skills), experience_satisfied,
        )
        return result

    @staticmethod
    def _compute_score(
        required_skills: set[str], matched_skills: list[str], experience_satisfied: bool | None
    ) -> float:
        """Match Score, 0-100.

        Base = percentage of the JD's required skills present in the
        resume. Then an experience adjustment: meeting a stated minimum
        adds a small bonus, failing it applies a penalty, and an
        unstated/unparseable requirement changes nothing (never penalise
        an unknown - same principle as the decision gate).

        Why a flat coverage percentage and not weighted-by-importance:
        the JD text gives us no signal about which of its skills matter
        more. Inventing weights (first-mentioned = more important, say)
        would look more sophisticated while being an unvalidated guess.
        A transparent percentage is easier for HR to sanity-check and
        easier to defend when a candidate asks why they were screened
        out.

        If a JD lists no detectable skills there is nothing to score
        against, so this returns 0.0 - read that as "no signal", not as
        "bad candidate". The decision path treats that case as
        shortlisted (0 missing skills), so a 0.0 score there does not
        silently reject anyone.
        """

        if not required_skills:
            return 0.0

        coverage = len(matched_skills) / len(required_skills) * 100.0

        if experience_satisfied is True:
            coverage = min(100.0, coverage + 5.0)
        elif experience_satisfied is False:
            coverage = max(0.0, coverage - 25.0)

        return round(coverage, 1)

    @staticmethod
    def _build_reason(
        decision: MatchDecision,
        missing_skills: list[str],
        jd_min_years: int | None,
        candidate_years: int | None,
        experience_satisfied: bool | None,
    ) -> str:
        parts: list[str] = []

        if not missing_skills:
            parts.append("All required skills are present in the resume.")
        elif len(missing_skills) == 1:
            parts.append(f"Missing 1 required skill: {missing_skills[0]}.")
        else:
            parts.append(f"Missing {len(missing_skills)} required skills: {', '.join(missing_skills)}.")

        if jd_min_years is not None:
            if experience_satisfied is True:
                parts.append(f"Meets the {jd_min_years}+ year experience requirement ({candidate_years} years found).")
            elif experience_satisfied is False:
                parts.append(
                    f"Does not meet the {jd_min_years}+ year experience requirement "
                    f"({candidate_years} years found)."
                )
            else:
                parts.append(
                    f"JD requires {jd_min_years}+ years of experience, but this could not be "
                    f"confirmed from the resume text."
                )

        verdict = "Shortlisted" if decision == MatchDecision.SHORTLISTED else "Not shortlisted"
        parts.append(f"Verdict: {verdict}.")
        return " ".join(parts)
