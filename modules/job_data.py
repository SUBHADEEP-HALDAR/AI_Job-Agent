"""Loading, validating and cleaning job records.

Two files are read:
- data/sample_jobs.json : clearly labelled fictional listings for testing
- data/my_jobs.json     : jobs YOU add yourself (via the app sidebar) from pages
                          you browse. Keep to sources whose terms allow this.
"""
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAMPLE_PATH = DATA_DIR / "sample_jobs.json"
MY_JOBS_PATH = DATA_DIR / "my_jobs.json"

REQUIRED_FIELDS = ("title", "company")
MAX_AGE_DAYS = 60


def _read(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def load_all_jobs() -> list:
    return _read(SAMPLE_PATH) + _read(MY_JOBS_PATH)


def save_my_job(job: dict) -> None:
    jobs = _read(MY_JOBS_PATH)
    job = dict(job)
    job["id"] = f"my-{len(jobs) + 1:03d}"
    job["last_checked"] = date.today().isoformat()
    job["active"] = True
    job["fictional"] = False
    jobs.append(job)
    MY_JOBS_PATH.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def is_valid_url(url) -> bool:
    try:
        p = urlparse(str(url or "").strip())
    except ValueError:
        return False
    return p.scheme in ("http", "https") and "." in p.netloc


def _parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def age_days(job: dict, today: date):
    d = _parse_date(job.get("last_checked"))
    return None if d is None else (today - d).days


def _key(job: dict) -> tuple:
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()
    return (norm(job.get("title")), norm(job.get("company")), norm(job.get("location")))


def clean_jobs(jobs: list, today: date = None, max_age_days: int = MAX_AGE_DAYS):
    """Validate, de-duplicate and drop expired jobs.

    Returns (kept_jobs, report). Each kept job gets 'url_valid' and 'age_days'.
    """
    today = today or date.today()
    report = {"loaded": len(jobs), "invalid": [], "inactive": [], "expired": [],
              "duplicates": [], "bad_urls": [], "kept": 0}
    candidates = []
    for j in jobs:
        label = f"{j.get('title', '?')} @ {j.get('company', '?')}"
        if any(not str(j.get(f) or "").strip() for f in REQUIRED_FIELDS):
            report["invalid"].append(label)
            continue
        if not j.get("active", True):
            report["inactive"].append(label)
            continue
        age = age_days(j, today)
        if age is not None and age > max_age_days:
            report["expired"].append(label)
            continue
        j = dict(j)
        j["age_days"] = age
        j["url_valid"] = is_valid_url(j.get("application_url"))
        if not j["url_valid"]:
            report["bad_urls"].append(label)
        candidates.append(j)

    # de-duplicate: keep the most recently checked record per (title, company, location)
    best = {}
    for j in candidates:
        k = _key(j)
        prev = best.get(k)
        if prev is None:
            best[k] = j
            continue
        newer = (j["age_days"] if j["age_days"] is not None else 9999) < \
                (prev["age_days"] if prev["age_days"] is not None else 9999)
        loser = prev if newer else j
        report["duplicates"].append(f"{loser.get('title')} @ {loser.get('company')}")
        if newer:
            best[k] = j
    kept = list(best.values())
    report["kept"] = len(kept)
    return kept, report
