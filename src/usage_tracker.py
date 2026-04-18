"""Daily API usage tracking for Groq and Gemini free-tier quota monitoring.

Usage resets automatically at midnight (local date).
Override default limits via .env:
  GROQ_DAILY_TOKEN_LIMIT   (default 28800)
  GROQ_DAILY_REQ_LIMIT     (default 500)
  GEMINI_DAILY_TOKEN_LIMIT (default 250000)
  GEMINI_DAILY_REQ_LIMIT   (default 1500)
"""
import os
import json
from datetime import date
from pathlib import Path

_USAGE_PATH = Path(__file__).parent.parent / "data" / "api_usage.json"

# Approximate free-tier daily limits — override via environment variables
GROQ_DAILY_TOKENS     = int(os.getenv("GROQ_DAILY_TOKEN_LIMIT",   "28800"))
GROQ_DAILY_REQUESTS   = int(os.getenv("GROQ_DAILY_REQ_LIMIT",     "500"))
GEMINI_DAILY_TOKENS   = int(os.getenv("GEMINI_DAILY_TOKEN_LIMIT", "250000"))
GEMINI_DAILY_REQUESTS = int(os.getenv("GEMINI_DAILY_REQ_LIMIT",   "1500"))


def _blank() -> dict:
    return {
        "date":   str(date.today()),
        "groq":   {"requests": 0, "tokens": 0},
        "gemini": {"requests": 0, "tokens": 0},
    }


def _load() -> dict:
    if not _USAGE_PATH.exists():
        return _blank()
    try:
        with open(_USAGE_PATH) as f:
            data = json.load(f)
        if data.get("date") != str(date.today()):
            return _blank()
        return data
    except Exception:
        return _blank()


def _save(data: dict):
    _USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_USAGE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def record_groq(tokens: int = 0):
    """Increment Groq daily request count and token total."""
    data = _load()
    data["groq"]["requests"] += 1
    data["groq"]["tokens"] += max(0, tokens)
    _save(data)


def record_gemini(tokens: int = 0):
    """Increment Gemini daily request count and token total."""
    data = _load()
    data["gemini"]["requests"] += 1
    data["gemini"]["tokens"] += max(0, tokens)
    _save(data)


def get_usage() -> dict:
    """Return today's usage: {date, groq: {requests, tokens}, gemini: {requests, tokens}}."""
    return _load()


def get_limits() -> dict:
    """Return configured daily limits."""
    return {
        "groq":   {"tokens": GROQ_DAILY_TOKENS,   "requests": GROQ_DAILY_REQUESTS},
        "gemini": {"tokens": GEMINI_DAILY_TOKENS, "requests": GEMINI_DAILY_REQUESTS},
    }
