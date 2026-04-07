import json
import re
from pathlib import Path

RED_FLAGS = [
    r"no sponsorship",
    r"u\.s\.?\s*citizen",
    r"us citizen",
    r"green card required",
    r"no c2c",
    r"not eligible for sponsorship",
    r"must be a citizen",
]

GREEN_FLAGS = [
    r"visa sponsorship",
    r"h1b",
    r"opt friendly",
    r"sponsor visa",
]

_RED_PATTERN = re.compile("|".join(RED_FLAGS), re.IGNORECASE)
_GREEN_PATTERN = re.compile("|".join(GREEN_FLAGS), re.IGNORECASE)


def filter_eligible_jobs(json_filepath):
    """
    Load job postings from json_filepath and filter out jobs with visa red flags.

    Returns a list of kept jobs, each annotated with a 'visa_status' key:
      - "Sponsored"      : description contains a green flag
      - "Unknown/Neutral": description contains neither red nor green flags

    Jobs containing any red flag are discarded entirely.
    """
    with open(json_filepath, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Support both a plain list and an envelope like {"data": [...]}
    if isinstance(payload, list):
        jobs = payload
    elif isinstance(payload, dict):
        jobs = payload.get("data", [])
    else:
        raise ValueError(f"Unexpected JSON structure in {json_filepath}")

    kept = []
    discarded = 0

    for job in jobs:
        try:
            description = job["description"]
        except KeyError:
            job["visa_status"] = "Unknown/Neutral"
            kept.append(job)
            continue

        if _RED_PATTERN.search(description):
            discarded += 1
            continue

        job["visa_status"] = "Sponsored" if _GREEN_PATTERN.search(description) else "Unknown/Neutral"
        kept.append(job)

    return kept, discarded


if __name__ == "__main__":
    # Resolve raw_jobs.json relative to the project root (one level up from src/)
    project_root = Path(__file__).parent.parent
    filepath = project_root / "raw_jobs.json"

    kept_jobs, discarded_count = filter_eligible_jobs(filepath)

    print(f"Jobs kept    : {len(kept_jobs)}")
    print(f"Jobs discarded: {discarded_count}")
    print(f"Total processed: {len(kept_jobs) + discarded_count}")
