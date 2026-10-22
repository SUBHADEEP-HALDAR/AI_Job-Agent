"""Deterministic, explainable job matching.

Score = weighted sum of five factors (initial weights, NOT validated yet):
  skills 35 | eligibility 25 | evidence 20 | preferences 10 | quality 10
The result is a RELATIVE fit score, not a hiring probability.
"""
import re
from datetime import date

from . import skills as sk
from .resume_parser import education_level, profile_evidence_text, EDU_LABELS

WEIGHTS = {"skills": 35, "eligibility": 25, "evidence": 20, "preferences": 10, "quality": 10}

EDU_REQ = {"none": 0, "diploma": 1, "bachelor": 2, "master": 3, "phd": 4}
# level -> (min_years, max_years or None)
LEVEL_YEARS = {"internship": (0, 1), "fresher": (0, 1), "0-2 years": (0, 2), "2+ years": (2, None)}
_SENIORITY = {"junior", "jr", "senior", "sr", "associate", "trainee", "intern", "executive"}

BREAKDOWN_LABELS = {
    "skills": "Skills alignment",
    "eligibility": "Eligibility",
    "evidence": "Evidence in projects/work",
    "preferences": "Your preferences",
    "quality": "Listing quality/freshness",
}


def _norm_level(level: str) -> str:
    return str(level or "").lower().replace("–", "-").replace("—", "-").strip()


def _skill_map(items) -> dict:
    out = {}
    for s in items or []:
        c = sk.canon(s)
        if c:
            out[c.lower()] = c
    return out


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z]+", str(text or "").lower()) if t not in _SENIORITY}


def _join(names, limit=8) -> str:
    names = list(names)
    s = ", ".join(names[:limit])
    return s + (f" (+{len(names) - limit} more)" if len(names) > limit else "")


def keyword_baseline(profile: dict, job: dict) -> float:
    """Naive baseline: share of ALL job skills the candidate lists (0-100)."""
    cand = _skill_map(profile.get("skills"))
    all_job = _skill_map(job.get("required_skills", [])) | _skill_map(job.get("preferred_skills", []))
    return round(100 * len(set(cand) & set(all_job)) / len(all_job), 1) if all_job else 0.0


def score_job(profile: dict, prefs: dict, job: dict, today: date = None) -> dict:
    today = today or date.today()
    reasons, gaps = [], []

    cand = _skill_map(profile.get("skills"))
    req = _skill_map(job.get("required_skills"))
    pref = _skill_map(job.get("preferred_skills"))

    # 1. skills --------------------------------------------------------------
    req_hit = [req[k] for k in req if k in cand]
    req_miss = [req[k] for k in req if k not in cand]
    pref_hit = [pref[k] for k in pref if k in cand]
    pref_miss = [pref[k] for k in pref if k not in cand]
    req_cov = len(req_hit) / len(req) if req else 1.0
    if pref:
        skills_frac = 0.75 * req_cov + 0.25 * (len(pref_hit) / len(pref))
    else:
        skills_frac = req_cov
    if req:
        reasons.append(f"You list {len(req_hit)} of {len(req)} required skills"
                       + (f": {_join(req_hit)}" if req_hit else ""))
    if pref_hit:
        reasons.append(f"Nice-to-have skills you have: {_join(pref_hit)}")
    if req_miss:
        gaps.append(f"Missing required skills: {_join(req_miss)}")
    if pref_miss:
        gaps.append(f"Nice-to-have you don't list: {_join(pref_miss)}")

    # 2. eligibility ---------------------------------------------------------
    excluded, exclusion_reason = False, ""
    years = float(profile.get("years_experience") or 0)
    lo, hi = LEVEL_YEARS.get(_norm_level(job.get("experience_level")), (0, None))
    if "min_years" in job:
        lo = float(job["min_years"])
    if years + 0.25 < lo:
        exp_frac = 0.0
        excluded, exclusion_reason = True, f"Needs about {lo:g}+ years of experience (you have {years:g})"
        gaps.append(exclusion_reason)
    elif hi is not None and years > hi + 2:
        exp_frac = 0.6
        gaps.append(f"May be below your level: aimed at up to {hi:g} years, you have {years:g}")
    else:
        exp_frac = 1.0
        reasons.append(f"Experience level fits ({job.get('experience_level', 'n/a')})")

    cand_edu = education_level(" ".join(profile.get("education", [])))
    need_edu = EDU_REQ.get(str(job.get("min_education", "none")).lower(), 0)
    if need_edu == 0:
        edu_frac = 1.0
    elif cand_edu is None:
        edu_frac = 0.5
        gaps.append(f"Education not found in your profile (job asks for {job.get('min_education')})")
    elif cand_edu >= need_edu:
        edu_frac = 1.0
        reasons.append(f"Education meets the {job.get('min_education')} requirement")
    else:
        edu_frac = 0.0
        msg = f"Requires {job.get('min_education')} degree (profile shows {EDU_LABELS[cand_edu]})"
        gaps.append(msg)
        if not excluded:
            excluded, exclusion_reason = True, msg
    eligibility_frac = 0.5 * exp_frac + 0.5 * edu_frac

    # 3. evidence ------------------------------------------------------------
    matched = req_hit + pref_hit
    ev_text = profile_evidence_text(profile)
    shown = [s for s in matched if sk.mentions(ev_text, s)]
    evidence_frac = len(shown) / len(matched) if matched else 0.0
    if shown:
        reasons.append(f"Shown in your projects/experience: {_join(shown)}")
    unshown = [s for s in req_hit if s not in shown]
    if unshown:
        gaps.append(f"Listed but not backed by a project/experience: {_join(unshown)}")

    # 4. preferences ---------------------------------------------------------
    role_tokens = _tokens(prefs.get("role"))
    if role_tokens:
        role_frac = len(role_tokens & _tokens(job.get("title"))) / len(role_tokens)
        if role_frac >= 0.99:
            reasons.append("Job title matches your preferred role")
    else:
        role_frac = 0.5

    loc_pref = [t.strip().lower() for t in re.split(r"[,/;]", str(prefs.get("location") or "")) if t.strip()]
    job_loc = str(job.get("location", "")).lower()
    job_mode = str(job.get("work_mode", "")).title()
    if not loc_pref:
        loc_frac = 0.5
    elif any(t in job_loc for t in loc_pref if t != "remote") or \
            ("remote" in loc_pref and job_mode == "Remote"):
        loc_frac = 1.0
        reasons.append(f"Location fits ({job.get('location')})")
    elif job_mode == "Remote":
        loc_frac = 0.6
        reasons.append("Remote role (location-independent)")
    else:
        loc_frac = 0.0
        gaps.append(f"Location differs: {job.get('location')}")

    want_mode = prefs.get("work_mode", "Any")
    mode_frac = 1.0 if want_mode in ("Any", "", None) or want_mode == job_mode else 0.3
    if mode_frac < 1.0:
        gaps.append(f"Work arrangement is {job_mode}, you prefer {want_mode}")
    want_level = _norm_level(prefs.get("level"))
    level_frac = 1.0 if want_level == _norm_level(job.get("experience_level")) else 0.5
    pref_frac = 0.45 * role_frac + 0.30 * loc_frac + 0.15 * mode_frac + 0.10 * level_frac

    # 5. quality / freshness -------------------------------------------------
    fields = ["title", "company", "location", "experience_level", "required_skills", "application_url"]
    complete = sum(1 for f in fields if job.get(f)) / len(fields)
    age = job.get("age_days")
    if age is None:
        fresh = 0.3
    elif age <= 14:
        fresh = 1.0
    else:
        fresh = max(0.0, 1 - (age - 14) / 46)
    url_ok = 1.0 if job.get("url_valid", True) else 0.0
    if not url_ok:
        gaps.append("Application link could not be validated")
    quality_frac = 0.4 * url_ok + 0.3 * complete + 0.3 * fresh

    fractions = {"skills": skills_frac, "eligibility": eligibility_frac,
                 "evidence": evidence_frac, "preferences": pref_frac, "quality": quality_frac}
    breakdown = {k: round(WEIGHTS[k] * v, 1) for k, v in fractions.items()}
    total = round(sum(breakdown.values()), 1)

    return {
        "job": job,
        "score": total,
        "breakdown": breakdown,
        "reasons": reasons,
        "gaps": gaps,
        "excluded": excluded,
        "exclusion_reason": exclusion_reason,
        "baseline": keyword_baseline(profile, job),
    }


def rank_jobs(profile: dict, prefs: dict, jobs: list, today: date = None) -> list:
    """Score all jobs. Eligible jobs first (by score), excluded jobs last."""
    results = [score_job(profile, prefs, j, today) for j in jobs]
    results.sort(key=lambda r: (r["excluded"], -r["score"], r["job"].get("title", "")))
    # baseline rank (over all results) for comparison
    by_base = sorted(results, key=lambda r: -r["baseline"])
    for i, r in enumerate(by_base, 1):
        r["baseline_rank"] = i
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return results
