import re
import requests
from bs4 import BeautifulSoup
from src.ollama_client import generate

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_job_url(url):
    """
    Scrape a job posting URL and return the page text.
    Returns (page_text, error_message).
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return None, f"Failed to fetch URL: {e}"

    soup = BeautifulSoup(response.text, "lxml")

    # Remove script, style, nav, footer clutter
    for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
        tag.decompose()

    # Try to find the main job content area
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", class_=re.compile(r"job|posting|description|content", re.I))
        or soup.find("body")
    )

    text = main_content.get_text(separator="\n", strip=True) if main_content else soup.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    # Truncate to avoid blowing up the local model's context window
    if len(text) > 8000:
        text = text[:8000]

    if len(text) < 50:
        return None, "Page content too short — the site may require login or JavaScript rendering."

    return text, None


def extract_job_details(url, page_text):
    """
    Use the local Ollama model to extract structured job details from raw page text.
    Returns (job_dict, error_message).
    """
    prompt = f"""You are a job posting data extractor. Given the raw text scraped from a job listing page,
extract the following fields. If a field is not found, use "Not specified".

Return EXACTLY this format (one field per line, no extra text, no markdown code fences):
JOB_TITLE: <the job title>
COMPANY: <the company name>
LOCATION: <city, state or remote>
SALARY: <salary range if mentioned, otherwise "Not specified">
EMPLOYMENT_TYPE: <full-time, part-time, contract, etc.>
DESCRIPTION: <the full job description including responsibilities and requirements — include as much detail as available>

URL: {url}

PAGE TEXT:
{page_text}"""

    text, err = generate(prompt, temperature=0.1)
    if err:
        return None, err
    return _parse_extraction(text, url), None


def _parse_extraction(text, url):
    """Parse the structured extraction response into a job dict."""
    fields = {}
    current_key = None
    current_value = []

    for line in text.split("\n"):
        # Check if this line starts a new field
        matched = False
        for key in ["JOB_TITLE", "COMPANY", "LOCATION", "SALARY", "EMPLOYMENT_TYPE", "DESCRIPTION"]:
            if line.strip().upper().startswith(key + ":"):
                # Save previous field
                if current_key:
                    fields[current_key] = "\n".join(current_value).strip()
                current_key = key
                current_value = [line.split(":", 1)[1].strip() if ":" in line else ""]
                matched = True
                break
        if not matched and current_key:
            current_value.append(line)

    # Save last field
    if current_key:
        fields[current_key] = "\n".join(current_value).strip()

    return {
        "job_title": fields.get("JOB_TITLE", "Not specified"),
        "company": fields.get("COMPANY", "Not specified"),
        "location": fields.get("LOCATION", "Not specified"),
        "salary_string": fields.get("SALARY", ""),
        "employment_type": fields.get("EMPLOYMENT_TYPE", ""),
        "description": fields.get("DESCRIPTION", ""),
        "apply_url": url,
        "source_url": url,
    }


def scrape_and_extract(url):
    """
    Full pipeline: scrape URL -> extract details with Ollama.
    Returns (job_dict, error_message).
    """
    page_text, err = scrape_job_url(url)
    if err:
        return None, err

    job_details, err = extract_job_details(url, page_text)
    if err:
        return None, err

    return job_details, None
