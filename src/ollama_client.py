import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def _using_gemini():
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def _using_groq():
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def check_groq_connection():
    """Test Groq specifically. Returns ("ok" | "unreachable", message)."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return "unreachable", "No Groq key set."
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=10,
        )
        r.raise_for_status()
        return "ok", f"Groq connected — {GROQ_MODEL}"
    except Exception as e:
        return "unreachable", f"Groq error: {e}"


def check_gemini_connection():
    """Test Gemini specifically via google-genai SDK. Returns ("ok" | "unreachable", message)."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "unreachable", "No Gemini key set."
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        client.models.generate_content(
            model=GEMINI_MODEL,
            contents="hi",
            config=types.GenerateContentConfig(max_output_tokens=1),
        )
        return "ok", f"Gemini connected — {GEMINI_MODEL}"
    except Exception as e:
        return "unreachable", f"Gemini error: {e}"


def check_connection():
    """
    Test the active backend.
    Returns ("ok" | "unreachable", message).
    """
    if _using_groq():
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                },
                timeout=10,
            )
            r.raise_for_status()
            return "ok", f"Groq connected — {GROQ_MODEL}"
        except Exception as e:
            return "unreachable", f"Groq error: {e}"

    if _using_gemini():
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={os.getenv('GEMINI_API_KEY')}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": "hi"}]}],
                    "generationConfig": {"maxOutputTokens": 1},
                },
                timeout=10,
            )
            r.raise_for_status()
            return "ok", f"Gemini connected — {GEMINI_MODEL}"
        except Exception as e:
            return "unreachable", f"Gemini error: {e}"

    return "unreachable", "No API key set — paste a Groq or Gemini key in the sidebar."


def generate(prompt, json_mode=False, temperature=0.2, num_predict=None, force_gemini=False):
    """Synchronous generation.
    Short prompts (<8k chars): Groq first, Gemini fallback.
    Long prompts (>=8k chars) or force_gemini=True: Gemini first.
    """
    prefer_gemini = force_gemini or len(prompt) >= 8_000
    if prefer_gemini:
        if _using_gemini():
            return _gemini_generate(prompt, json_mode=json_mode, temperature=temperature, max_tokens=num_predict)
        if _using_groq():
            return _groq_generate(prompt, json_mode=json_mode, temperature=temperature, max_tokens=num_predict)
    else:
        if _using_groq():
            return _groq_generate(prompt, json_mode=json_mode, temperature=temperature, max_tokens=num_predict)
        if _using_gemini():
            return _gemini_generate(prompt, json_mode=json_mode, temperature=temperature, max_tokens=num_predict)
    return None, "No API key set — paste a Groq or Gemini key in the sidebar."


def generate_stream(prompt, json_mode=False, temperature=0.2, num_predict=None, force_gemini=False):
    """Streaming generation.
    Short prompts (<8k chars): Groq first, Gemini fallback.
    Long prompts (>=8k chars) or force_gemini=True: Gemini first.
    """
    prefer_gemini = force_gemini or len(prompt) >= 8_000
    if prefer_gemini:
        if _using_gemini():
            return _gemini_stream(prompt, json_mode=json_mode, temperature=temperature, max_tokens=num_predict)
        if _using_groq():
            return _groq_stream(prompt, json_mode=json_mode, temperature=temperature, max_tokens=num_predict)
    else:
        if _using_groq():
            return _groq_stream(prompt, json_mode=json_mode, temperature=temperature, max_tokens=num_predict)
        if _using_gemini():
            return _gemini_stream(prompt, json_mode=json_mode, temperature=temperature, max_tokens=num_predict)
    return None, "No API key set — paste a Groq or Gemini key in the sidebar."


# ── Groq helpers ──────────────────────────────────────────────────────────────

_GROQ_PROMPT_LIMIT = 20_000


def _groq_generate(prompt, json_mode=False, temperature=0.2, max_tokens=None):
    """Non-streaming call to Groq. Retries on 429."""
    import time
    prompt = prompt[:_GROQ_PROMPT_LIMIT]
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens or 2048,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    for attempt in range(4):
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if r.status_code == 429:
                wait = int(r.headers.get("retry-after", 2 ** attempt * 5))
                time.sleep(wait)
                continue
            r.raise_for_status()
            resp_data = r.json()
            content = resp_data["choices"][0]["message"]["content"].strip()
            try:
                from src.usage_tracker import record_groq
                record_groq(resp_data.get("usage", {}).get("total_tokens", 0))
            except Exception:
                pass
            return content, None
        except requests.exceptions.HTTPError:
            if attempt < 3:
                time.sleep(2 ** attempt * 5)
                continue
            return None, f"Groq error: {r.status_code} after retries"
        except Exception as e:
            return None, f"Groq error: {e}"
    return None, "Groq rate limit — try again in a minute"


def _groq_stream(prompt, json_mode=False, temperature=0.2, max_tokens=None):
    """Streaming call to Groq."""
    prompt = prompt[:_GROQ_PROMPT_LIMIT]
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens or 2048,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
            stream=True,
        )
        response.raise_for_status()

        def stream_generator():
            _total_tokens = 0
            try:
                for line in response.iter_lines():
                    if not line:
                        continue
                    text = line.decode("utf-8") if isinstance(line, bytes) else line
                    if text.startswith("data: "):
                        text = text[6:]
                    if text == "[DONE]":
                        break
                    try:
                        chunk = json.loads(text)
                        # Groq sends a final usage chunk with choices=[]
                        usage = chunk.get("usage")
                        if usage and isinstance(usage, dict) and usage.get("total_tokens"):
                            _total_tokens = usage["total_tokens"]
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                    except Exception:
                        continue
            except Exception:
                pass
            finally:
                try:
                    from src.usage_tracker import record_groq
                    record_groq(_total_tokens)
                except Exception:
                    pass

        return stream_generator(), None
    except Exception as e:
        return None, f"Groq error: {e}"


# ── Gemini helpers (google-genai SDK) ────────────────────────────────────────

def _gemini_client():
    from google import genai
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY", "").strip())


def _gemini_generate(prompt, json_mode=False, temperature=0.2, max_tokens=None):
    """Non-streaming call via google-genai SDK."""
    try:
        from google import genai
        from google.genai import types
        client = _gemini_client()
        cfg = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens or 2048,
        )
        if json_mode:
            cfg.response_mime_type = "application/json"
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=cfg,
        )
        try:
            from src.usage_tracker import record_gemini
            meta = response.usage_metadata
            record_gemini(meta.total_token_count if meta else 0)
        except Exception:
            pass
        return response.text.strip(), None
    except Exception as e:
        return None, f"Gemini error: {e}"


def _gemini_stream(prompt, json_mode=False, temperature=0.2, max_tokens=None):
    """Streaming call via google-genai SDK."""
    try:
        from google import genai
        from google.genai import types
        client = _gemini_client()
        cfg = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens or 4096,
        )
        if json_mode:
            cfg.response_mime_type = "application/json"

        def stream_generator():
            _total_tokens = 0
            try:
                for chunk in client.models.generate_content_stream(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=cfg,
                ):
                    if chunk.text:
                        yield chunk.text
                    try:
                        if chunk.usage_metadata and chunk.usage_metadata.total_token_count:
                            _total_tokens = chunk.usage_metadata.total_token_count
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                try:
                    from src.usage_tracker import record_gemini
                    record_gemini(_total_tokens)
                except Exception:
                    pass

        return stream_generator(), None
    except Exception as e:
        return None, f"Gemini error: {e}"
