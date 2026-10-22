
import requests

print("Himalayas API test started")

BASE_URL = "https://himalayas.app/jobs/api/search"

def test_search(label, params):
    print(f"\n--- {label} ---")

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

        jobs = data.get("jobs", [])
        print("Total matching jobs:", data.get("totalCount", len(jobs)))

        for job in jobs[:5]:
            print(
                f"- {job.get('title', 'Unknown title')} "
                f"at {job.get('companyName', 'Unknown company')}"
            )
            print("  Apply:", job.get("applicationLink", "No link"))

    except requests.RequestException as error:
        print("API request failed:", error)
    except ValueError:
        print("The API did not return valid JSON.")

test_search(
    "India-based remote jobs",
    {"q": "data analyst", "country": "IN", "page": 1}
)

test_search(
    "Worldwide remote jobs",
    {"q": "data analyst", "worldwide": "true", "page": 1}
)
