"""Live job search helpers for the Adzuna API.

This module is designed for app_Job.py:
- build_query(prefs, profile)
- search_adzuna(app_id, app_key, what, where, country)
- attribution_url(country)
- JobSourceError
"""
from datetime import date
import re

import requests

from . import skills as sk


API_ROOT = "https://api.adzuna.com/v1/api/jobs"
RESULTS_PER_PAGE = 20
TIMEOUT_SECONDS = 15


class JobSourceError(RuntimeError):
    """A safe, user-facing error from a live job source."""


def build_query(prefs: dict, profile: dict) -> tuple[str, str]:
    """Build a job-title/keyword query and a location query from user preferences."""
    role = str((prefs or {}).get("role") or "").strip()
    location = str((prefs or {}).get("location") or "").strip()

    if not role:
        skills = (profile or {}).get("skills") or []
        # Keep the query short; skills are only used when the user did not enter a role.
        role = " ".join(str(s).strip() for s in skills[:3] if str(s).strip())

    # Avoid sending a very long string to the API.
    role = re.sub(r"\s+", " ", role)[:120]
    location = re.sub(r"\s+", " ", location)[:120]
    return role or "graduate entry level", location


def _extract_skills(text: str) -> list[str]:
    """Infer known skills from the listing text using the app's existing taxonomy."""
    try:
        return sk.find_skills(text or "")
    except (AttributeError, TypeError):
        return []


def _experience_level(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if any(term in text for term in ("internship", "intern ", "intern-", "internship")):
        return "Internship"
    if any(term in text for term in ("senior", "lead ", "principal", "manager", "director")):
        return "2+ years"
    if any(term in text for term in ("junior", "entry level", "entry-level", "graduate", "fresher", "trainee")):
        return "Fresher"
    return "0–2 years"


def _work_mode(title: str, description: str, location: str) -> str:
    text = f"{title} {description} {location}".lower()
    if "remote" in text or "work from home" in text or "work-from-home" in text:
        return "Remote"
    if "hybrid" in text:
        return "Hybrid"
    return "On-site"


def _created_date(value) -> str:
    """Return a YYYY-MM-DD date if Adzuna provided one; otherwise today's date."""
    raw = str(value or "").strip()
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return date.today().isoformat()


def search_adzuna(app_id: str, app_key: str, what: str, where: str, country: str = "in") -> list[dict]:
    """Search Adzuna and normalize results into the job schema used by job_matcher."""
    if not str(app_id or "").strip() or not str(app_key or "").strip():
        raise JobSourceError("Live jobs are not configured. Add ADZUNA_APP_ID and ADZUNA_APP_KEY in Streamlit secrets.")

    country = re.sub(r"[^a-z]", "", str(country or "in").lower()) or "in"
    url = f"{API_ROOT}/{country}/search/1"
    params = {
        "app_id": str(app_id).strip(),
        "app_key": str(app_key).strip(),
        "results_per_page": RESULTS_PER_PAGE,
        "what": str(what or "").strip()[:120],
        "where": str(where or "").strip()[:120],
        "content-type": "application/json",
        "sort_by": "date",
    }

    try:
        response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    except requests.Timeout as exc:
        raise JobSourceError("Adzuna took too long to respond. Please try again.") from exc
    except requests.RequestException as exc:
        raise JobSourceError("Could not connect to Adzuna. Check your connection and try again.") from exc

    if response.status_code in (401, 403):
        raise JobSourceError("Adzuna rejected the API credentials. Check ADZUNA_APP_ID and ADZUNA_APP_KEY.")
    if response.status_code == 429:
        raise JobSourceError("Adzuna rate limit reached. Please wait before searching again.")
    if response.status_code >= 500:
        raise JobSourceError("Adzuna is temporarily unavailable. Please try again later.")
    if not response.ok:
        raise JobSourceError(f"Adzuna returned an error (HTTP {response.status_code}). Check the country code and search terms.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise JobSourceError("Adzuna returned an unreadable response.") from exc

    raw_jobs = payload.get("results", []) if isinstance(payload, dict) else []
    jobs = []
    for item in raw_jobs:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        company_obj = item.get("company") or {}
        location_obj = item.get("location") or {}
        company = str(company_obj.get("display_name") or "Company not listed").strip()
        location = str(location_obj.get("display_name") or where or "Location not listed").strip()
        description = str(item.get("description") or "")
        application_url = str(item.get("redirect_url") or "").strip()
        skills = _extract_skills(f"{title} {description}")

        # The API's created date is used as a freshness estimate; it is not the
        # date we fetched the listing. job_data.clean_jobs reads last_checked.
        jobs.append({
            "id": str(item.get("id") or ""),
            "title": title,
            "company": company,
            "location": location,
            "work_mode": _work_mode(title, description, location),
            "experience_level": _experience_level(title, description),
            "min_education": "none",
            "required_skills": skills,
            "preferred_skills": [],
            "application_url": application_url,
            "source": "Adzuna",
            "last_checked": _created_date(item.get("created")),
            "active": True,
            "fictional": False,
            "live": True,
            "description": description[:2000],
        })

    return jobs


def attribution_url(country: str = "in") -> str:
    """Return an Adzuna site URL for attribution."""
    country = re.sub(r"[^a-z]", "", str(country or "in").lower()) or "in"
    country_domains = {
        "gb": "https://www.adzuna.co.uk/",
        "us": "https://www.adzuna.com/",
        "au": "https://www.adzuna.com.au/",
        "ca": "https://www.adzuna.ca/",
        "in": "https://www.adzuna.in/",
        "za": "https://www.adzuna.co.za/",
        "de": "https://www.adzuna.de/",
        "fr": "https://www.adzuna.fr/",
        "nl": "https://www.adzuna.nl/",
        "br": "https://www.adzuna.com.br/",
        "nz": "https://www.adzuna.co.nz/",
        "sg": "https://www.adzuna.sg/",
    }
    return country_domains.get(country, "https://www.adzuna.com/")
