import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from modules import job_data, job_matcher, job_sources
from modules import resume_parser as rp
from modules import skills as sk

PROFILE_PATH = Path(__file__).parent / "data" / "profile.json"
LEVELS = ["Fresher", "Internship", "0–2 years", "2+ years"]


def _public_mode() -> bool:
    """True when deployed publicly. Set PUBLIC_MODE = "true" in Streamlit secrets.

    In public mode nothing is written to the server's disk (no saved profile,
    no added jobs), so visitors can never see each other's data.
    """
    value = os.getenv("PUBLIC_MODE", "false")
    try:
        value = st.secrets.get("PUBLIC_MODE", value)
    except Exception:  # no secrets file locally
        pass
    return str(value).strip().lower() in ("1", "true", "yes")


PUBLIC = _public_mode()
MAX_LIVE_SEARCHES = 15  # per browser session, to protect the shared API key
ADZUNA_LOGO = Path(__file__).parent / "assets" / "adzuna.png"


def _secret(name: str) -> str:
    """Read a setting from Streamlit secrets or an environment variable."""
    value = os.getenv(name, "")
    try:
        value = st.secrets.get(name, value)
    except Exception:  # no secrets file locally
        pass
    return str(value or "").strip()


@st.cache_data(ttl=6 * 3600, show_spinner="Fetching live jobs…")
def fetch_live_jobs(what: str, where: str, country: str, app_id: str, app_key: str) -> list:
    """Cached for 6 hours so repeated identical searches don't use up API quota."""
    return job_sources.search_adzuna(app_id, app_key, what, where, country)

st.set_page_config(page_title="AI Job Finder", page_icon="🔎", layout="wide")

# ------------------------------------------------------------------ helpers
def to_lines(text: str) -> list:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def to_skills(text: str) -> list:
    out, seen = [], set()
    for tok in (text or "").replace("\n", ",").split(","):
        c = sk.canon(tok.strip())
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def save_profile(profile: dict) -> None:
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")


def set_profile(profile: dict) -> None:
    st.session_state.profile = profile
    st.session_state.pver = st.session_state.get("pver", 0) + 1
    st.session_state.pop("results", None)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("About")
    st.caption(
        "Personal-use version. Your resume is read in memory and never uploaded "
        "anywhere except this app. Scores show relative fit, not hiring chances."
    )

    st.subheader("Saved profile")
    if PUBLIC:
        st.caption("Saving is turned off in the public version. Nothing you upload is stored.")
    elif PROFILE_PATH.exists():
        c1, c2 = st.columns(2)
        if c1.button("Load"):
            set_profile(json.loads(PROFILE_PATH.read_text(encoding="utf-8")))
            st.rerun()
        if c2.button("Delete"):
            PROFILE_PATH.unlink()
            st.success("Saved profile deleted.")
            st.rerun()
    else:
        st.caption("Nothing saved yet. Save after reviewing your profile.")

    if not PUBLIC:
        with st.expander("➕ Add a job I found"):
            st.caption("Add listings you found yourself, from sources whose terms allow it.")
            with st.form("add_job", clear_on_submit=True):
                t = st.text_input("Job title *")
                co = st.text_input("Company *")
                loc = st.text_input("Location")
                mode = st.selectbox("Work mode", ["On-site", "Hybrid", "Remote"])
                lvl = st.selectbox("Experience level", ["Fresher", "Internship", "0-2 years", "2+ years"])
                edu = st.selectbox("Minimum education", ["none", "diploma", "bachelor", "master", "phd"])
                req = st.text_input("Required skills (comma separated)")
                nice = st.text_input("Preferred skills (comma separated)")
                url = st.text_input("Original application URL *")
                src = st.text_input("Source", value="Added by me")
                if st.form_submit_button("Save job"):
                    if not (t.strip() and co.strip() and job_data.is_valid_url(url)):
                        st.error("Title, company and a valid http(s) URL are required.")
                    else:
                        job_data.save_my_job({
                            "title": t.strip(), "company": co.strip(), "location": loc.strip(),
                            "work_mode": mode, "experience_level": lvl, "min_education": edu,
                            "required_skills": to_skills(req), "preferred_skills": to_skills(nice),
                            "application_url": url.strip(), "source": src.strip() or "Added by me",
                        })
                        st.success("Job saved.")

# --------------------------------------------------------------------- main
st.title("🔎 AI Job-Finding Assistant")
st.write("Upload your resume, check what was extracted, and get a ranked, explained shortlist.")

# ---- Step 1: resume --------------------------------------------------------
st.header("1. Your resume")
tab_up, tab_manual = st.tabs(["Upload PDF / DOCX", "Enter skills manually"])

with tab_up:
    resume = st.file_uploader("Choose a PDF or DOCX file (max 5 MB)", type=["pdf", "docx"])
    if st.button("Read resume", disabled=resume is None):
        try:
            text = rp.extract_text(resume.getvalue(), resume.name)
            set_profile(rp.parse_resume_text(text))
            st.success("Resume read. Please review the extracted profile below.")
        except rp.ResumeError as e:
            st.error(str(e))

with tab_manual:
    manual = st.text_area("Your skills, comma separated", placeholder="Python, SQL, Excel, Power BI")
    if st.button("Start with these skills", disabled=not manual.strip()):
        p = rp.empty_profile()
        p["skills"] = to_skills(manual)
        set_profile(p)

# ---- Step 2: review profile ------------------------------------------------
profile = st.session_state.get("profile")
if profile:
    st.header("2. Review and correct your profile")
    v = st.session_state.get("pver", 0)
    with st.form("profile_form"):
        skills_txt = st.text_area("Skills (comma separated)", ", ".join(profile["skills"]),
                                  key=f"skills_{v}", height=90)
        c1, c2 = st.columns(2)
        edu_txt = c1.text_area("Education (one per line)", "\n".join(profile["education"]),
                               key=f"edu_{v}", height=120)
        proj_txt = c2.text_area("Projects (one per line)", "\n".join(profile["projects"]),
                                key=f"proj_{v}", height=120)
        c3, c4 = st.columns(2)
        intern_txt = c3.text_area("Internships", "\n".join(profile["internships"]),
                                  key=f"int_{v}", height=120)
        exp_txt = c4.text_area("Work experience", "\n".join(profile["experience"]),
                               key=f"exp_{v}", height=120)
        cert_txt = st.text_area("Certifications", "\n".join(profile["certifications"]),
                                key=f"cert_{v}", height=80)
        years = st.number_input("Years of full-time experience (internships don't count)",
                                min_value=0.0, max_value=40.0, step=0.5,
                                value=float(profile["years_experience"]), key=f"yrs_{v}")
        saved = st.form_submit_button("Confirm profile")
    if saved:
        profile = {
            "skills": to_skills(skills_txt), "education": to_lines(edu_txt),
            "projects": to_lines(proj_txt), "internships": to_lines(intern_txt),
            "experience": to_lines(exp_txt), "certifications": to_lines(cert_txt),
            "years_experience": float(years),
        }
        st.session_state.profile = profile
        st.session_state.pop("results", None)
        st.success("Profile confirmed.")
    lvl = rp.education_level(" ".join(profile["education"]))
    st.caption(f"Highest education detected: {rp.EDU_LABELS[lvl]} · "
               f"{len(profile['skills'])} skills in profile")
    if not PUBLIC and st.button("💾 Save profile on this computer"):
        save_profile(profile)
        st.success("Saved to data/profile.json (listed in .gitignore).")

    # ---- Step 3: preferences ----------------------------------------------
    st.header("3. Your preferences")
    p1, p2, p3, p4 = st.columns(4)
    role = p1.text_input("Preferred job role", placeholder="e.g. Data Analyst")
    location = p2.text_input("Preferred location", placeholder="e.g. Kolkata, Remote")
    level = p3.selectbox("Target experience level", LEVELS)
    work_mode = p4.selectbox("Work arrangement", ["Any", "Remote", "Hybrid", "On-site"])
    prefs = {"role": role, "location": location, "level": level, "work_mode": work_mode}

    # ---- Step 4: results --------------------------------------------------
    st.header("4. Matching jobs")
    app_id, app_key = _secret("ADZUNA_APP_ID"), _secret("ADZUNA_APP_KEY")
    country = (_secret("ADZUNA_COUNTRY") or "in").lower()
    live_ready = bool(app_id and app_key)
    sources = (["Live jobs (Adzuna)"] if live_ready else []) + ["Sample jobs (fictional)"]
    source = st.radio("Job source", sources, horizontal=True)
    use_live = source.startswith("Live")
    if not live_ready:
        st.info("Live jobs are off because no Adzuna API keys are set. "
                "See 'Live jobs' in the README. Until then only fictional sample jobs are shown.")
    else:
        st.caption("Live search sends only your role and location keywords to Adzuna. "
                   "Your resume and profile are never sent.")

    if st.button("Find matching jobs", type="primary"):
        live_jobs, error = [], None
        if use_live:
            if st.session_state.get("live_calls", 0) >= MAX_LIVE_SEARCHES:
                error = "Live search limit reached for this session. Reload the page to continue."
            else:
                st.session_state.live_calls = st.session_state.get("live_calls", 0) + 1
                what, where = job_sources.build_query(prefs, profile)
                try:
                    live_jobs = fetch_live_jobs(what, where, country, app_id, app_key)
                except job_sources.JobSourceError as e:
                    error = str(e)
        if error:
            st.error(error)
            st.session_state.pop("results", None)
        else:
            jobs, report = job_data.clean_jobs(
                live_jobs + job_data.load_all_jobs(include_sample=not use_live),
                today=date.today())
            st.session_state.results = job_matcher.rank_jobs(profile, prefs, jobs, today=date.today())
            st.session_state.report = report
            st.session_state.result_country = country
            if use_live and not live_jobs:
                st.warning("Adzuna returned no jobs for that search. Try a broader role or location.")

    report = st.session_state.get("report")
    if report:
        with st.expander(f"Job data quality: {report['kept']} of {report['loaded']} records usable"):
            st.write({k: (v if not isinstance(v, list) else (v or "none")) for k, v in report.items()})
            st.caption("Sample jobs are fictional and dated for testing. Live jobs come from Adzuna, "
                       "with skills and experience level inferred from short listing snippets.")

    results = st.session_state.get("results")
    if results is not None:
        f1, f2 = st.columns(2)
        min_score = f1.slider("Minimum score", 0, 100, 30)
        show_excl = f2.checkbox("Also show jobs I'm not eligible for", value=False)
        shown = [r for r in results if r["score"] >= min_score and (show_excl or not r["excluded"])]
        st.caption("Scores are a relative fit estimate, not a hiring probability. "
                   "Weights are initial values and not yet validated.")
        if not shown:
            st.info("No jobs above this score. Try lowering the minimum or adding more skills.")

        for r in shown:
            job = r["job"]
            with st.container(border=True):
                left, right = st.columns([4, 1])
                left.subheader(f"{r['rank']}. {job['title']} — {job['company']}")
                left.caption(
                    f"{job.get('location', '')} · {job.get('work_mode', '')} · "
                    f"{job.get('experience_level', '')} · Source: {job.get('source', '')} · "
                    f"Last checked: {job.get('last_checked', 'unknown')}"
                )
                right.metric("Fit score", f"{r['score']:.0f}/100")
                if r["excluded"]:
                    st.warning(f"Not eligible: {r['exclusion_reason']}")
                a, b = st.columns(2)
                with a:
                    st.markdown("**Why it matches**")
                    for x in r["reasons"] or ["No strong matches found."]:
                        st.markdown(f"- {x}")
                with b:
                    st.markdown("**Gaps to know about**")
                    for x in r["gaps"] or ["No major gaps found."]:
                        st.markdown(f"- {x}")
                if job.get("url_valid"):
                    st.link_button("Open original application page", job["application_url"])
                else:
                    st.caption("No valid application link on this record.")
                if job.get("fictional"):
                    st.caption("⚠ Sample listing (fictional) for testing.")
                if job.get("live"):
                    site = job_sources.attribution_url(st.session_state.get("result_country", "in"))
                    if ADZUNA_LOGO.exists():
                        st.image(str(ADZUNA_LOGO), width=116)
                    st.caption(f"Jobs by [Adzuna]({site})")
                with st.expander("Score breakdown"):
                    st.dataframe(pd.DataFrame([
                        {"Factor": job_matcher.BREAKDOWN_LABELS[k], "Points": pts,
                         "Max": job_matcher.WEIGHTS[k]}
                        for k, pts in r["breakdown"].items()
                    ]), hide_index=True)

        with st.expander("Compare with a simple keyword baseline"):
            st.caption("Baseline = share of the job's skills found in your profile. "
                       "If the baseline ranks things similarly, the extra logic isn't adding much.")
            st.dataframe(pd.DataFrame([
                {"Rank": r["rank"], "Job": f"{r['job']['title']} — {r['job']['company']}",
                 "Score": r["score"], "Baseline rank": r["baseline_rank"],
                 "Baseline %": r["baseline"], "Eligible": not r["excluded"]}
                for r in results
            ]), hide_index=True)
else:
    st.info("Upload a resume or enter your skills above to begin.")
