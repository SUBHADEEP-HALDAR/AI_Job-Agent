# AI Job Finder (personal-use version)

Upload a resume → review the extracted profile → get ranked, explained job matches → open the original application page.

Runs locally on your computer. Botpress, accounts, a database and deployment are intentionally left for a later upgrade.

## Run it (Windows PowerShell)

```powershell
cd ai-job-finder
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

On macOS/Linux activate with `source .venv/bin/activate`.

## How to use

1. Upload a text-based PDF or DOCX (or type your skills) and click **Read resume**.
2. Fix the extracted profile and click **Confirm profile**. Corrections matter: they drive the score.
3. Set role, location, level and work arrangement.
4. Click **Find matching jobs**.

## Jobs

- `data/sample_jobs.json` holds 34 **fictional** listings, including deliberate bad records (duplicate, stale, inactive, invalid URL) to prove the cleaning works. Their `last_checked` dates age out after 60 days; update them to keep testing.
- To get real results, use **Add a job I found** in the sidebar. Entries go to `data/my_jobs.json`. Only add listings from sources whose terms allow it, and don't scrape sites that forbid it.

## Scoring (initial, unvalidated weights)

| Factor | Points |
|---|---|
| Skills alignment (required + preferred) | 35 |
| Eligibility (experience level, education) | 25 |
| Evidence (skills shown in projects/work) | 20 |
| Your preferences (role, location, mode, level) | 10 |
| Listing quality/freshness (valid link, complete, recent) | 10 |

It is a relative fit score, not a hiring probability. Jobs that fail a hard requirement (too much experience required, degree too low) are hidden by default and ranked last. Salary is not scored because the job records have no reliable salary field.

Check the weights by comparing the top results with your own judgement, and use the **keyword baseline** table in the app to see whether the logic beats naive keyword counting.

## Customising

- Missing skills? Add aliases in `modules/skills.py`.
- Change weights in `modules/job_matcher.py` (`WEIGHTS`).

## Privacy

- The resume is read in memory and its text isn't logged or stored. Only the profile you confirm can be saved, to `data/profile.json`, via the button. Delete it from the sidebar.
- `.gitignore` excludes your profile, added jobs, PDFs and DOCX files. Don't commit them.

## Later upgrades (not built yet)

Botpress assistant → controlled API → permitted live job sources → hosted database with login → Streamlit Community Cloud deployment.
