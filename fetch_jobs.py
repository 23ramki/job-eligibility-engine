import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

URL = "https://api.theirstack.com/v1/jobs/search"

DEFAULT_PAYLOAD = {
    "job_title_or": ["Data Analyst", "Business Analyst"],
    "job_location_pattern_or": ["Dallas", "Richardson"],
    "posted_at_max_age_days": 1,
    "limit": 50,
}


def fetch_jobs_from_api(payload=None):
    """
    Fetch jobs from TheirStack API.
    Returns (jobs_list, error_message). On success error_message is None.
    """
    api_key = os.getenv("THEIRSTACK_API_KEY")
    if not api_key:
        return [], "THEIRSTACK_API_KEY is not set in your .env file."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if payload is None:
        payload = DEFAULT_PAYLOAD

    try:
        response = requests.post(URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Save a local backup
        backup_path = os.path.join(os.path.dirname(__file__), "raw_jobs.json")
        with open(backup_path, "w") as f:
            json.dump(data, f, indent=2)

        jobs = data.get("data", []) if isinstance(data, dict) else data
        return jobs, None

    except requests.exceptions.Timeout:
        return [], "API request timed out. Try again later."
    except requests.exceptions.HTTPError as e:
        return [], f"API error: {e.response.status_code} — {e.response.text[:200]}"
    except Exception as e:
        return [], f"Failed to fetch jobs: {e}"


def load_jobs_from_file(filepath="raw_jobs.json"):
    """Load jobs from a local JSON file as a fallback."""
    full_path = os.path.join(os.path.dirname(__file__), filepath)
    if not os.path.exists(full_path):
        return [], f"File not found: {filepath}"

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        jobs = data.get("data", []) if isinstance(data, dict) else data
        return jobs, None
    except Exception as e:
        return [], f"Error reading {filepath}: {e}"


if __name__ == "__main__":
    print("Fetching jobs from TheirStack...")
    jobs, err = fetch_jobs_from_api()
    if err:
        print(f"Error: {err}")
    else:
        print(f"Fetched {len(jobs)} jobs successfully.")
