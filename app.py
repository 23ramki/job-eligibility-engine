import os
import re
import uuid
import json
from datetime import datetime, timezone
import streamlit as st
from src.state_manager import (
    init_tracking_table, save_new_jobs,
    get_all_jobs_by_status, get_all_jobs, update_job_status, update_job_resume_summary,
    update_job_notes, search_jobs, get_job_stats, delete_job,
    update_job_fit_score, get_unscored_jobs,
    save_job_fit_analysis, get_job_fit_analysis,
)
from src.llm_tailoring import (
    generate_tailored_resume, generate_cover_letter,
    analyze_fit_and_ask_questions, edit_resume_with_instruction,
    quick_fit_score,
)
from src.pdf_generator import markdown_resume_to_pdf
from src.job_scraper import scrape_and_extract
from src.ollama_client import check_connection, check_groq_connection, check_gemini_connection

st.set_page_config(
    page_title="Job Eligibility CRM",
    layout="wide",
    page_icon="static/favicon.png",
)

# ── Theme init ──────────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.theme = "dark"
_THEME = st.session_state.theme

# ── Logo ────────────────────────────────────────────────────────────
_logo_path = f"static/logo-{'dark' if _THEME == 'dark' else 'light'}.png"
if os.path.exists(_logo_path):
    try:
        st.logo(_logo_path, size="large")
    except Exception:
        pass  # st.logo not available in older Streamlit builds

# ===================== APPLE-INSPIRED DESIGN SYSTEM =====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Design tokens — Apple dark (default) ── */
:root {
  --bg:            #000000;
  --surface:       #1C1C1E;
  --surface-2:     #2C2C2E;
  --surface-3:     #3A3A3C;
  --text:          #FFFFFF;
  --text-2:        rgba(255,255,255,0.72);
  --muted:         #8E8E93;
  --line:          rgba(255,255,255,0.08);
  --line-strong:   rgba(255,255,255,0.14);
  --accent:        #0A84FF;
  --accent-hover:  #409CFF;
  --accent-text:   #FFFFFF;
  --accent-bg:     rgba(10,132,255,0.10);
  --accent-border: rgba(10,132,255,0.30);
  --shadow:        0 4px 24px rgba(0,0,0,0.55), 0 1px 4px rgba(0,0,0,0.35);
  --shadow-sm:     0 2px 8px rgba(0,0,0,0.35), 0 1px 2px rgba(0,0,0,0.2);
  --radius:        12px;
  --radius-sm:     8px;
  --font:          -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", sans-serif;
  --font-display:  -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif;
}

/* ── Base ── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stApp"], .stApp {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: var(--font) !important;
  line-height: 1.5;
}

/* ── Typography ── */
h1, h2, h3, h4 {
  font-family: var(--font-display) !important;
  letter-spacing: -0.02em !important;
  color: var(--text) !important;
}
h1 { font-size: clamp(1.75rem, 4vw, 2.5rem) !important; font-weight: 700 !important; line-height: 1.1 !important; }
h2 { font-size: clamp(1.25rem, 2.5vw, 1.65rem) !important; font-weight: 600 !important; line-height: 1.2 !important; }
h3 { font-size: clamp(1rem, 2vw, 1.2rem) !important; font-weight: 600 !important; line-height: 1.3 !important; }

/* ── Header bar ── */
[data-testid="stHeader"] {
  background: rgba(0,0,0,0.75) !important;
  backdrop-filter: blur(24px) saturate(1.8) !important;
  -webkit-backdrop-filter: blur(24px) saturate(1.8) !important;
  border-bottom: 0.5px solid var(--line-strong) !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 0.5px solid var(--line-strong) !important;
}
[data-testid="stSidebar"] * {
  color: var(--text) !important;
}

/* ── Metric cards ── */
[data-testid="stMetric"] {
  background: var(--surface) !important;
  border: 0.5px solid var(--line-strong) !important;
  border-radius: var(--radius) !important;
  padding: 1.25rem 1.5rem !important;
  box-shadow: var(--shadow-sm) !important;
}
[data-testid="stMetricValue"] {
  font-family: var(--font-display) !important;
  font-weight: 700 !important;
  font-size: clamp(1.75rem, 4vw, 2.4rem) !important;
  letter-spacing: -0.02em !important;
  color: var(--accent) !important;
}
[data-testid="stMetricLabel"] {
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  color: var(--muted) !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
}

/* ── Buttons ── */
.stButton > button {
  font-family: var(--font) !important;
  font-weight: 500 !important;
  font-size: 0.9rem !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
  border-radius: var(--radius-sm) !important;
  transition: all 0.18s ease !important;
  cursor: pointer !important;
}
/* Primary — Apple blue */
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: var(--accent) !important;
  color: var(--accent-text) !important;
  border: none !important;
  box-shadow: 0 1px 4px rgba(10,132,255,0.3) !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {
  background: var(--accent-hover) !important;
  box-shadow: 0 4px 16px rgba(10,132,255,0.40) !important;
  transform: translateY(-1px) !important;
}
/* Secondary — tinted surface */
.stButton > button[kind="secondary"],
.stButton > button[data-testid="baseButton-secondary"] {
  background: var(--surface-2) !important;
  color: var(--text) !important;
  border: 0.5px solid var(--line-strong) !important;
}
.stButton > button[kind="secondary"]:hover,
.stButton > button[data-testid="baseButton-secondary"]:hover {
  background: var(--surface-3) !important;
  transform: translateY(-1px) !important;
}

/* Link buttons */
.stLinkButton a {
  font-family: var(--font) !important;
  font-weight: 500 !important;
  font-size: 0.9rem !important;
  letter-spacing: 0 !important;
  text-transform: none !important;
  border-radius: var(--radius-sm) !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
  background: var(--surface-2) !important;
  color: var(--text) !important;
  border: 0.5px solid var(--line-strong) !important;
  border-radius: var(--radius-sm) !important;
  font-family: var(--font) !important;
  font-size: 0.9rem !important;
  transition: border-color 0.18s ease, box-shadow 0.18s ease !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(10,132,255,0.18) !important;
  outline: none !important;
}
.stTextInput label, .stTextArea label {
  color: var(--muted) !important;
  font-size: 0.8rem !important;
  font-weight: 500 !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
}

/* ── Select / Dropdown ── */
.stSelectbox > div > div,
.stSelectbox [data-baseweb="select"] > div {
  background: var(--surface-2) !important;
  border: 0.5px solid var(--line-strong) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text) !important;
}
.stSelectbox [data-baseweb="select"] > div:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(10,132,255,0.18) !important;
}
[data-baseweb="menu"] {
  background: var(--surface) !important;
  border: 0.5px solid var(--line-strong) !important;
  border-radius: var(--radius-sm) !important;
  box-shadow: var(--shadow) !important;
}
[data-baseweb="menu"] li {
  color: var(--text) !important;
  font-family: var(--font) !important;
}
[data-baseweb="menu"] li:hover {
  background: var(--accent-bg) !important;
  color: var(--accent) !important;
}

/* ── Expanders (job cards) ── */
[data-testid="stExpander"] {
  background: var(--surface) !important;
  border: 0.5px solid var(--line-strong) !important;
  border-radius: var(--radius) !important;
  box-shadow: var(--shadow-sm) !important;
  margin-bottom: 0.5rem !important;
  overflow: hidden !important;
  transition: box-shadow 0.18s ease !important;
}
[data-testid="stExpander"]:hover {
  box-shadow: var(--shadow) !important;
}
[data-testid="stExpander"] summary {
  font-family: var(--font) !important;
  font-weight: 500 !important;
  font-size: 0.95rem !important;
  color: var(--text) !important;
  padding: 1rem 1.25rem !important;
  cursor: pointer !important;
}
[data-testid="stExpander"] > div > div {
  padding: 0 1.25rem 1.25rem !important;
}

/* ── Tabs ── */
[data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 0.5px solid var(--line-strong) !important;
  gap: 0.25rem !important;
}
[data-baseweb="tab"] {
  font-family: var(--font) !important;
  font-weight: 500 !important;
  font-size: 0.875rem !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  color: var(--muted) !important;
  background: transparent !important;
  border-bottom: 2px solid transparent !important;
  transition: color 0.18s ease, border-color 0.18s ease !important;
  padding: 0.625rem 1rem !important;
}
[data-baseweb="tab"]:hover {
  color: var(--text) !important;
}
[aria-selected="true"][data-baseweb="tab"] {
  color: var(--accent) !important;
  border-bottom-color: var(--accent) !important;
}
[data-baseweb="tab-panel"] {
  background: transparent !important;
  padding-top: 1.25rem !important;
}

/* ── Radio buttons (view/sort toggles) ── */
.stRadio > div {
  gap: 0.4rem !important;
  flex-direction: row !important;
  flex-wrap: wrap !important;
}
.stRadio label {
  font-family: var(--font) !important;
  font-weight: 500 !important;
  font-size: 0.875rem !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  color: var(--muted) !important;
  background: var(--surface-2) !important;
  border: 0.5px solid var(--line-strong) !important;
  border-radius: var(--radius-sm) !important;
  padding: 0.4rem 1rem !important;
  cursor: pointer !important;
  transition: all 0.18s ease !important;
}
.stRadio label:has(input:checked) {
  color: var(--accent-text) !important;
  background: var(--accent) !important;
  border-color: var(--accent) !important;
}

/* ── Dividers ── */
hr {
  border: none !important;
  border-top: 0.5px solid var(--line-strong) !important;
  margin: 1.25rem 0 !important;
}

/* ── Caption / small text ── */
.stCaption, small, [data-testid="stCaptionContainer"] {
  color: var(--muted) !important;
  font-size: 0.78rem !important;
}

/* ── Alerts / notifications ── */
[data-testid="stNotification"], .stAlert {
  border-radius: var(--radius-sm) !important;
  border-left: 3px solid var(--accent) !important;
  background: var(--surface) !important;
  border-top: 0.5px solid var(--line-strong) !important;
  border-right: 0.5px solid var(--line-strong) !important;
  border-bottom: 0.5px solid var(--line-strong) !important;
}
[data-testid="stNotification"] p, .stAlert p {
  color: var(--text) !important;
}

/* ── Spinner ── */
.stSpinner > div {
  border-top-color: var(--accent) !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--line-strong);
  border-radius: 100px;
}
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

/* ── Text selection ── */
::selection {
  background: var(--accent);
  color: var(--accent-text);
}

/* ── Kanban columns ── */
[data-testid="stHorizontalBlock"] > [data-testid="column"] {
  background: var(--surface) !important;
  border: 0.5px solid var(--line-strong) !important;
  border-radius: var(--radius) !important;
  padding: 0.75rem 0.5rem !important;
  box-shadow: var(--shadow-sm) !important;
}

/* ── Download button ── */
.stDownloadButton > button {
  font-family: var(--font) !important;
  font-weight: 500 !important;
  font-size: 0.9rem !important;
  background: var(--accent) !important;
  color: var(--accent-text) !important;
  border: none !important;
  border-radius: var(--radius-sm) !important;
  transition: all 0.18s ease !important;
}
.stDownloadButton > button:hover {
  background: var(--accent-hover) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 16px rgba(10,132,255,0.35) !important;
}

/* ── Chat messages ── */
[data-testid="chatMessage"] {
  background: var(--surface) !important;
  border: 0.5px solid var(--line-strong) !important;
  border-radius: var(--radius-sm) !important;
}
[data-testid="stChatInput"] > div {
  background: var(--surface-2) !important;
  border: 0.5px solid var(--line-strong) !important;
  border-radius: var(--radius-sm) !important;
}
[data-testid="stChatInput"] input {
  background: transparent !important;
  color: var(--text) !important;
  font-family: var(--font) !important;
}
[data-testid="stChatInput"] > div:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(10,132,255,0.18) !important;
}

/* ── Checkbox ── */
.stCheckbox label {
  color: var(--text) !important;
  font-family: var(--font) !important;
}

/* ── Expander body text ── */
[data-testid="stExpander"] .stMarkdown p {
  color: var(--text-2) !important;
  font-size: 0.9rem !important;
  line-height: 1.6 !important;
}
[data-testid="stExpander"] .stMarkdown strong {
  color: var(--text) !important;
}

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div {
  background: var(--accent) !important;
}

/* ── Reduce motion ── */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
</style>
""", unsafe_allow_html=True)

# ── Light-mode CSS override — Apple light (white + blue) ──
if _THEME == "light":
    st.markdown("""
<style>
:root {
  --bg:            #F2F2F7 !important;
  --surface:       #FFFFFF !important;
  --surface-2:     #F2F2F7 !important;
  --surface-3:     #E5E5EA !important;
  --text:          #000000 !important;
  --text-2:        rgba(0,0,0,0.65) !important;
  --muted:         #6E6E73 !important;
  --line:          rgba(60,60,67,0.08) !important;
  --line-strong:   rgba(60,60,67,0.18) !important;
  --accent:        #007AFF !important;
  --accent-hover:  #0071E3 !important;
  --accent-text:   #FFFFFF !important;
  --accent-bg:     rgba(0,122,255,0.08) !important;
  --accent-border: rgba(0,122,255,0.28) !important;
  --shadow:        0 4px 24px rgba(0,0,0,0.10), 0 1px 4px rgba(0,0,0,0.06) !important;
  --shadow-sm:     0 2px 8px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04) !important;
}
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stApp"], .stApp {
  background: #F2F2F7 !important;
  color: #000000 !important;
}
[data-testid="stHeader"] {
  background: rgba(242,242,247,0.80) !important;
  border-bottom: 0.5px solid rgba(60,60,67,0.18) !important;
}
[data-testid="stSidebar"] {
  background: #FFFFFF !important;
  border-right: 0.5px solid rgba(60,60,67,0.14) !important;
}
[data-testid="stSidebar"] * { color: #000000 !important; }
</style>
""", unsafe_allow_html=True)

# --- Initialize DB ---
try:
    init_tracking_table()
except Exception as e:
    st.error(f"Failed to initialize database: {e}")
    st.stop()

# --- Load master resume ---
resume_path = os.path.join("data", "master_resume.txt")
master_resume = ""
if os.path.exists(resume_path):
    with open(resume_path, "r", encoding="utf-8") as f:
        master_resume = f.read()

PLACEHOLDER = "Replace this file with your actual master resume text."
has_resume = master_resume and master_resume.strip() != PLACEHOLDER

# Status display config
STATUS_EMOJI = {"New": "🆕", "Applied": "📤", "Interviewing": "💬", "Rejected": "❌"}
VISA_BADGE = {"Sponsored": "🟢 Sponsored", "Unknown/Neutral": "⚪ Unknown/Neutral"}


def _update_env_file(key, value):
    """Persist a key=value pair to the .env file."""
    env_path = ".env"
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
    updated = False
    for idx, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[idx] = f"{key}={value}\n"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)


def _collect_stream(gen):
    """Consume a generator silently and return the full text."""
    return "".join(gen)


FIT_SCORE_TIERS = [
    (80, "🟢", "Strong Match"),
    (60, "🟡", "Good Fit"),
    (40, "🟠", "Partial Fit"),
    (0,  "🔴", "Weak Fit"),
]


def _fit_icon(score):
    """Return the emoji for a given fit score."""
    if score is None:
        return "⬜"
    for threshold, icon, _ in FIT_SCORE_TIERS:
        if score >= threshold:
            return icon
    return "🔴"


# ===================== SIDEBAR =====================
with st.sidebar:
    # ── Theme toggle ──────────────────────────────
    _toggle_label = "☀️  Light Mode" if _THEME == "dark" else "🌙  Dark Mode"
    if st.button(_toggle_label, use_container_width=True, key="theme_toggle"):
        st.session_state.theme = "light" if _THEME == "dark" else "dark"
        st.rerun()
    st.markdown("---")

    st.header("Add a Job")
    st.caption("Paste a job listing URL — we'll extract everything automatically.")

    job_url = st.text_input(
        "Job URL",
        placeholder="https://linkedin.com/jobs/view/...",
        label_visibility="collapsed",
    )

    if st.button("Add Job from URL", type="primary", use_container_width=True):
        if not job_url or not job_url.startswith("http"):
            st.error("Please paste a valid URL.")
        else:
            with st.spinner("Scraping job page and extracting details..."):
                job_details, err = scrape_and_extract(job_url.strip())

            if err:
                st.error(f"Could not extract job: {err}")
                st.info("Try the manual entry below instead.")
            else:
                job_details["id"] = str(uuid.uuid4())[:8]
                job_details["visa_status"] = "Unknown/Neutral"
                count = save_new_jobs([job_details])
                if count:
                    st.success(f"Added: **{job_details['job_title']}** at {job_details['company']}")
                    if has_resume and job_details.get("description"):
                        with st.spinner("Scoring fit against your resume..."):
                            fit_result, _ = quick_fit_score(
                                job_details["job_title"], job_details["company"],
                                job_details["description"], master_resume,
                            )
                        if fit_result:
                            update_job_fit_score(
                                job_details["id"],
                                fit_result["score"],
                                fit_result["label"],
                                fit_result.get("reason", ""),
                            )
                            st.info(f"{_fit_icon(fit_result['score'])} Fit score: **{fit_result['score']}/100** — {fit_result['label']}")
                    st.rerun()
                else:
                    st.error("Failed to save job.")

    # Manual fallback
    with st.expander("Manual entry (if URL doesn't work)"):
        with st.form("manual_job_form", clear_on_submit=True):
            m_title = st.text_input("Job Title")
            m_company = st.text_input("Company")
            m_url = st.text_input("Apply URL")
            m_location = st.text_input("Location")
            m_description = st.text_area("Job Description", height=150)
            m_submitted = st.form_submit_button("Add Manually")

        if m_submitted:
            if not m_title or not m_company:
                st.error("Title and Company are required.")
            else:
                manual_job = [{
                    "id": str(uuid.uuid4())[:8],
                    "job_title": m_title.strip(),
                    "company": m_company.strip(),
                    "location": m_location.strip(),
                    "url": m_url.strip(),
                    "description": m_description.strip(),
                    "visa_status": "Unknown/Neutral",
                }]
                count = save_new_jobs(manual_job)
                if count:
                    st.success(f"Added: {m_title} at {m_company}")
                    st.rerun()

    st.markdown("---")

    # --- Resume editor ---
    st.subheader("Master Resume")
    if not has_resume:
        st.warning("Add your resume below to enable AI tailoring.")

    edited_resume = st.text_area(
        "Edit your resume",
        value=master_resume,
        height=350,
        label_visibility="collapsed",
    )
    word_count = len(edited_resume.split()) if edited_resume else 0
    st.caption(f"{word_count} words")
    if st.button("Save Resume", use_container_width=True):
        os.makedirs("data", exist_ok=True)
        with open(resume_path, "w", encoding="utf-8") as f:
            f.write(edited_resume)
        master_resume = edited_resume
        has_resume = master_resume and master_resume.strip() != PLACEHOLDER
        st.success("Resume saved!")

    st.markdown("---")

    # --- AI Engine ---
    st.subheader("☁️ AI Engine")
    st.caption("Set both keys for smart routing: Groq handles quick scoring, Gemini handles full-resume operations.")

    _gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    _groq_key   = os.getenv("GROQ_API_KEY", "").strip()

    # ── Groq ──────────────────────────────────────────
    new_groq = st.text_input(
        "Groq API Key (console.groq.com)",
        value=_groq_key,
        type="password",
        placeholder="gsk_...",
        label_visibility="visible",
    )
    groq_save_col, groq_test_col = st.columns(2)
    with groq_save_col:
        if st.button("Save", use_container_width=True, key="save_groq"):
            os.environ["GROQ_API_KEY"] = new_groq.strip()
            _update_env_file("GROQ_API_KEY", new_groq.strip())
            st.success("Groq key saved!")
            st.rerun()
    with groq_test_col:
        if st.button("Test Groq ↗", use_container_width=True, key="test_groq"):
            with st.spinner("Testing Groq…"):
                s, m = check_groq_connection()
            if s == "ok":
                st.success(f"🟢 {m}")
            else:
                st.error(f"🔴 {m}")

    st.markdown("")

    # ── Gemini ────────────────────────────────────────
    new_gemini = st.text_input(
        "Gemini API Key (aistudio.google.com)",
        value=_gemini_key,
        type="password",
        placeholder="AIza...",
        label_visibility="visible",
    )
    _gemini_model_current = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    new_gemini_model = st.text_input(
        "Gemini Model",
        value=_gemini_model_current,
        placeholder="gemini-2.5-flash-lite",
        label_visibility="visible",
        help="Try: gemini-2.5-flash-lite · gemini-2.5-flash · gemini-2.0-flash-lite",
    )
    gem_save_col, gem_test_col = st.columns(2)
    with gem_save_col:
        if st.button("Save", use_container_width=True, key="save_gemini"):
            os.environ["GEMINI_API_KEY"] = new_gemini.strip()
            _update_env_file("GEMINI_API_KEY", new_gemini.strip())
            if new_gemini_model.strip():
                os.environ["GEMINI_MODEL"] = new_gemini_model.strip()
                _update_env_file("GEMINI_MODEL", new_gemini_model.strip())
            st.success("Gemini key saved!")
            st.rerun()
    with gem_test_col:
        if st.button("Test Gemini ↗", use_container_width=True, key="test_gemini"):
            with st.spinner("Testing Gemini…"):
                s, m = check_gemini_connection()
            if s == "ok":
                st.success(f"🟢 {m}")
            else:
                st.error(f"🔴 {m}")

    st.markdown("---")

    # --- API Usage Today ---
    from src.usage_tracker import get_usage as _get_usage, get_limits as _get_limits
    _usage  = _get_usage()
    _limits = _get_limits()
    _groq_active   = bool(os.getenv("GROQ_API_KEY", "").strip())
    _gemini_active = bool(os.getenv("GEMINI_API_KEY", "").strip())

    if _groq_active or _gemini_active:
        with st.expander("📊 API Usage Today", expanded=True):
            if _groq_active:
                g_req = _usage["groq"]["requests"]
                g_tok = _usage["groq"]["tokens"]
                g_req_lim = _limits["groq"]["requests"]
                g_tok_lim = _limits["groq"]["tokens"]
                st.markdown("**Groq**")
                st.progress(
                    min(g_req / max(g_req_lim, 1), 1.0),
                    text=f"Requests: {g_req} / {g_req_lim}/day",
                )
                st.progress(
                    min(g_tok / max(g_tok_lim, 1), 1.0),
                    text=f"Tokens: {g_tok:,} / {g_tok_lim:,}/day",
                )

            if _gemini_active:
                m_req = _usage["gemini"]["requests"]
                m_tok = _usage["gemini"]["tokens"]
                m_req_lim = _limits["gemini"]["requests"]
                m_tok_lim = _limits["gemini"]["tokens"]
                if _groq_active:
                    st.markdown("")
                st.markdown("**Gemini**")
                st.progress(
                    min(m_req / max(m_req_lim, 1), 1.0),
                    text=f"Requests: {m_req} / {m_req_lim}/day",
                )
                st.progress(
                    min(m_tok / max(m_tok_lim, 1), 1.0),
                    text=f"Tokens: {m_tok:,} / {m_tok_lim:,}/day",
                )

            st.caption(
                "Limits are approximate free-tier defaults. "
                "Set GROQ_DAILY_TOKEN_LIMIT / GROQ_DAILY_REQ_LIMIT / "
                "GEMINI_DAILY_TOKEN_LIMIT / GEMINI_DAILY_REQ_LIMIT in .env to override. "
                "Resets at midnight."
            )

    st.markdown("---")

    # --- Batch Fit Scoring ---
    if has_resume:
        unscored = get_unscored_jobs()
        if unscored:
            st.subheader("Fit Scoring")
            st.caption(f"{len(unscored)} job{'s' if len(unscored) != 1 else ''} not yet scored.")
            if st.button(f"Score All {len(unscored)} Unscored", use_container_width=True, type="primary"):
                progress = st.progress(0, text="Scoring jobs…")
                scored, failed = 0, 0
                for i, job in enumerate(unscored):
                    if job.get("description"):
                        fit_result, err = quick_fit_score(
                            job["job_title"], job["company"],
                            job["description"], master_resume,
                        )
                        if fit_result:
                            update_job_fit_score(job["job_id"], fit_result["score"], fit_result["label"], fit_result.get("reason", ""))
                            scored += 1
                        else:
                            failed += 1
                    progress.progress((i + 1) / len(unscored), text=f"Scoring {i+1}/{len(unscored)}…")
                progress.empty()
                st.success(f"Scored {scored} job{'s' if scored != 1 else ''}." + (f" {failed} skipped (no description)." if failed else ""))
                st.rerun()
            st.markdown("---")

    # --- Stats ---
    stats = get_job_stats()
    added_today = stats.get("added_today", 0)
    st.metric("Total Jobs", stats["total"])
    st.progress(min(added_today / 70, 1.0), text=f"Today: {added_today} / 70 goal")
    stat_cols = st.columns(2)
    with stat_cols[0]:
        st.metric("Added Today", added_today)
    with stat_cols[1]:
        st.metric("Applied", stats["by_status"].get("Applied", 0))


# ===================== MAIN CONTENT =====================
st.title("Job Eligibility CRM")

# --- Search & Filter Bar ---
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([3, 1, 1, 1])
with filter_col1:
    search_query = st.text_input(
        "Search jobs",
        placeholder="Search by title, company, location, or keywords...",
    )
with filter_col2:
    status_filter = st.selectbox("Status", ["All", "New", "Applied", "Interviewing", "Rejected"])
with filter_col3:
    visa_filter = st.selectbox("Visa", ["All", "Sponsored", "Unknown/Neutral"])
with filter_col4:
    _fit_filter_opts = ["All Scores", "🟢 80+", "🟡 60+", "🟠 40+", "🔴 <40"]
    fit_score_filter = st.selectbox("Fit Score", _fit_filter_opts)

# --- View Mode & Sort ---
_vc, _sc = st.columns(2)
with _vc:
    view_mode = st.radio("View", ["List View", "Kanban Board"], horizontal=True, label_visibility="collapsed")
with _sc:
    _sort_label = st.radio("Sort", ["Newest First", "Best Fit"], index=1, horizontal=True, label_visibility="collapsed")
sort_by = "newest" if _sort_label == "Newest First" else "fit_score"


def _apply_fit_filter(jobs, score_filter):
    """Filter a job list by fit score band."""
    if score_filter == "🟢 80+":
        return [j for j in jobs if (j.get("fit_score") or 0) >= 80]
    if score_filter == "🟡 60+":
        return [j for j in jobs if (j.get("fit_score") or 0) >= 60]
    if score_filter == "🟠 40+":
        return [j for j in jobs if (j.get("fit_score") or 0) >= 40]
    if score_filter == "🔴 <40":
        return [j for j in jobs if j.get("fit_score") is not None and j["fit_score"] < 40]
    return jobs


if search_query or status_filter != "All" or visa_filter != "All" or fit_score_filter != "All Scores":
    filtered_jobs = search_jobs(search_query, status_filter, visa_filter, sort_by=sort_by)
    filtered_jobs = _apply_fit_filter(filtered_jobs, fit_score_filter)
    use_filtered = True
else:
    filtered_jobs = None
    use_filtered = False

# --- Onboarding banner ---
if not has_resume:
    st.info(
        "👈 **Get started:** Open the sidebar to add your master resume and set API keys — "
        "this unlocks AI fit scoring, tailored resumes, and cover letters."
    )

STATUSES = ["New", "Applied", "Interviewing", "Rejected"]


def _sync_analysis_score(job_id, analysis_data):
    """
    Extract the X/10 fit score from an analysis dict and update the DB.
    Called whenever a fresh analysis result is stored.
    """
    if not isinstance(analysis_data, dict):
        return
    fit_md = analysis_data.get("fit_analysis", "")
    match = re.search(r"(?:###\s*Fit Score[^\n]*\n\s*)(\d+)\s*/\s*10", fit_md)
    if not match:
        return
    score_10 = int(match.group(1))
    score_100 = score_10 * 10
    if score_100 >= 80:
        label = "Strong Match"
    elif score_100 >= 60:
        label = "Good Fit"
    elif score_100 >= 40:
        label = "Partial Fit"
    else:
        label = "Weak Fit"
    # Pull a one-line reason from the analysis markdown if possible
    reason_match = re.search(r"###\s*Fit Score[^\n]*\n(.+)", fit_md)
    reason = reason_match.group(1).strip().lstrip("—- ") if reason_match else ""
    update_job_fit_score(job_id, score_100, label, reason)


def render_job_card(job):
    """Render a job card with details, fit analysis, resume generation, and PDF download."""
    job_id = job["job_id"]
    title = job["job_title"] or "Untitled"
    company = job["company"] or "Unknown"
    location = job.get("location") or "Not specified"
    visa = job.get("visa_status") or "Unknown"
    apply_url = job.get("apply_url") or ""
    source_url = job.get("source_url") or ""
    salary = job.get("salary_string") or ""
    description = job.get("description") or ""
    seniority = job.get("seniority") or ""
    emp_type = job.get("employment_type") or ""
    date_posted = job.get("date_posted") or ""
    remote = job.get("remote")
    hybrid = job.get("hybrid")
    current_status = job.get("status") or "New"
    applied_at = job.get("applied_at") or ""

    # Tags
    tags = []
    if visa == "Sponsored":
        tags.append("🟢 Sponsored")
    if remote:
        tags.append("🌐 Remote")
    if hybrid:
        tags.append("🔀 Hybrid")
    if seniority:
        tags.append(seniority.replace("_", " ").title())
    if emp_type:
        tags.append(emp_type.replace("_", " ").title())

    fit_score = job.get("fit_score")
    fit_label = job.get("fit_label") or ""
    fit_reason = job.get("fit_reason") or ""
    fit_tag = f"  ·  {_fit_icon(fit_score)} {fit_score}/100" if fit_score is not None else "  ·  ⬜ Unscored"

    status_icon = STATUS_EMOJI.get(current_status, "")
    # Progress indicators: ✅ fit analysis done, 📄 tailored resume ready
    _has_analysis = bool(job.get("fit_analysis_json"))
    _has_resume_draft = bool(job.get("resume_summary") and job["resume_summary"].startswith("# "))
    _indicators = (" ✅" if _has_analysis else "") + (" 📄" if _has_resume_draft else "")
    expander_label = f"{status_icon} **{title}** — {company} | {location}{fit_tag}{_indicators}"

    # ── Quick actions — always visible, no expand needed ───────────────
    _hdr_c1, _hdr_c2, _hdr_spacer = st.columns([1, 1, 6])
    with _hdr_c1:
        if apply_url:
            st.link_button("Apply →", apply_url, use_container_width=True, type="primary")
    with _hdr_c2:
        if current_status == "New":
            if st.button("✓ Applied", key=f"qa_{job_id}", use_container_width=True):
                update_job_status(job_id, "Applied")
                st.rerun()

    with st.expander(expander_label):
        if tags:
            badges_html = "".join(
                f'<span style="display:inline-block;background:var(--accent-bg);'
                f'color:var(--accent);border:1px solid var(--accent-border);border-radius:6px;'
                f'padding:2px 9px;font-size:0.72rem;font-weight:500;'
                f'margin:0 5px 5px 0;">{tag}</span>'
                for tag in tags
            )
            st.markdown(f'<div style="margin-bottom:0.5rem;">{badges_html}</div>', unsafe_allow_html=True)

        if fit_reason:
            st.markdown(
                f'<div style="font-size:0.78rem;color:var(--muted);font-style:italic;'
                f'margin-bottom:0.75rem;">{_fit_icon(fit_score)} {fit_label} — {fit_reason}</div>',
                unsafe_allow_html=True,
            )

        # Notes — moved up for fast access without scrolling
        current_notes = job.get("notes") or ""
        notes = st.text_area("Notes", value=current_notes, key=f"notes_{job_id}", height=68,
                             placeholder="Quick notes, follow-up reminders...",
                             label_visibility="visible")
        notes_changed = notes != current_notes
        if st.button("Save Notes", key=f"savenotes_{job_id}", disabled=not notes_changed):
            update_job_notes(job_id, notes)
            st.success("Notes saved!")

        st.markdown("---")

        # Key info
        info_cols = st.columns([1, 1, 1, 1])
        with info_cols[0]:
            if date_posted:
                st.markdown(f"**Posted:** {date_posted}")
        with info_cols[1]:
            if salary:
                st.markdown(f"**Salary:** {salary}")
        with info_cols[2]:
            st.markdown(f"**Visa:** {VISA_BADGE.get(visa, visa)}")
        with info_cols[3]:
            if current_status == "Applied" and applied_at:
                try:
                    _applied_dt = datetime.strptime(applied_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                    _days = (datetime.now(timezone.utc) - _applied_dt).days
                    _days_str = "today" if _days == 0 else f"{_days}d ago"
                    st.markdown(f"**Applied:** {_days_str}")
                except Exception:
                    st.markdown("**Applied:** ✓")

        # Source link (apply is already at top; show source if different)
        if source_url and source_url != apply_url:
            st.link_button("View Job Source ↗", source_url)

        # Job description
        if description:
            st.markdown("**Job Description:**")
            with st.container(height=200):
                st.markdown(description[:5000])

        # Status & actions
        st.markdown("---")
        action_cols = st.columns([2, 1])
        with action_cols[0]:
            idx = STATUSES.index(current_status) if current_status in STATUSES else 0
            new_status = st.selectbox("Move to", STATUSES, index=idx, key=f"sel_{job_id}")
            if new_status != current_status:
                update_job_status(job_id, new_status)
                st.rerun()
        with action_cols[1]:
            # Two-step delete confirmation
            confirm_key = f"confirm_del_{job_id}"
            if st.session_state.get(confirm_key):
                st.warning("Delete this job?")
                yes_col, no_col = st.columns(2)
                with yes_col:
                    if st.button("Yes", key=f"del_yes_{job_id}", type="primary", use_container_width=True):
                        delete_job(job_id)
                        st.rerun()
                with no_col:
                    if st.button("No", key=f"del_no_{job_id}", use_container_width=True):
                        st.session_state[confirm_key] = False
                        st.rerun()
            else:
                st.markdown("&nbsp;", unsafe_allow_html=True)  # vertical spacer
                if st.button("🗑️ Delete", key=f"del_{job_id}", type="secondary", use_container_width=True):
                    st.session_state[confirm_key] = True
                    st.rerun()

        # ===================== AI RESUME TAILORING =====================
        if has_resume and description:
            st.markdown("---")
            st.subheader("AI Resume Tailoring")
            st.caption("Step 1 → Analyze Fit & answer questions  ·  Step 2 → Generate Tailored Resume  ·  Step 3 → Cover Letter")

            existing_resume = job.get("resume_summary") or ""

            tab_analysis, tab_resume, tab_cover = st.tabs([
                "1. Fit Analysis", "2. Tailored Resume", "3. Cover Letter"
            ])

            # --- TAB 1: Fit Analysis & Questions ---
            with tab_analysis:
                analysis_key = f"analysis_{job_id}"
                if analysis_key not in st.session_state:
                    # Load saved analysis from DB (persists across sessions)
                    st.session_state[analysis_key] = get_job_fit_analysis(job_id)

                analysis_data = st.session_state[analysis_key]

                if analysis_data:
                    # Reset button in top-right
                    hdr_col, reset_col = st.columns([5, 1])
                    with reset_col:
                        if st.button("↺ Reset", key=f"reset_analysis_{job_id}"):
                            st.session_state[analysis_key] = None
                            save_job_fit_analysis(job_id, None)
                            st.rerun()

                    if isinstance(analysis_data, dict):
                        fit_md = analysis_data.get("fit_analysis", "")
                        if fit_md:
                            st.markdown(fit_md)

                        questions = analysis_data.get("questions", [])
                        if questions:
                            st.markdown("---")
                            st.markdown("**Answer the questions below** to get a more accurate tailored resume:")
                            for i, q in enumerate(questions):
                                q_text = q.get("question", f"Question {i + 1}")
                                options = q.get("options", [])
                                options_with_other = options + ["Other (type your own)"]
                                selected = st.radio(
                                    q_text,
                                    options_with_other,
                                    key=f"q_{job_id}_{i}",
                                )
                                if selected == "Other (type your own)":
                                    st.text_input(
                                        "Your answer:",
                                        key=f"q_other_{job_id}_{i}",
                                        placeholder="Type your custom answer...",
                                    )
                        else:
                            st.success("All questions resolved — ready to generate your resume.")
                    else:
                        st.markdown(analysis_data)
                        st.markdown("---")
                        st.markdown("**Answer the questions above** to get a more accurate tailored resume:")
                        st.text_area(
                            "Your answers",
                            key=f"answers_{job_id}",
                            height=120,
                            placeholder="Type your answers here...",
                        )

                    if st.button("Regenerate Analysis with My Answers", key=f"regen_analysis_{job_id}"):
                        current_analysis = st.session_state.get(analysis_key)
                        if isinstance(current_analysis, dict):
                            questions = current_analysis.get("questions", [])
                            parts = []
                            for i, q in enumerate(questions):
                                q_text = q.get("question", f"Question {i + 1}")
                                selected = st.session_state.get(f"q_{job_id}_{i}", "")
                                if selected == "Other (type your own)":
                                    answer = st.session_state.get(f"q_other_{job_id}_{i}", "").strip()
                                else:
                                    answer = selected
                                if answer:
                                    parts.append(f"Q: {q_text}\nA: {answer}")
                            compiled_answers = "\n\n".join(parts)
                        else:
                            compiled_answers = st.session_state.get(f"answers_{job_id}", "")

                        status_slot = st.empty()
                        status_slot.info("Generating…")
                        gen, err = analyze_fit_and_ask_questions(
                            title, company, description, master_resume, compiled_answers
                        )
                        if err:
                            status_slot.error(err)
                        else:
                            raw_json = ""
                            char_count = 0
                            for chunk in gen:
                                raw_json += chunk
                                char_count += len(chunk)
                                status_slot.caption(f"Generating analysis… {char_count} chars received")
                            status_slot.empty()
                            if not raw_json.strip():
                                st.error("AI returned an empty response. Check your API key and try again.")
                            else:
                                try:
                                    parsed = json.loads(raw_json)
                                    st.session_state[analysis_key] = parsed
                                    save_job_fit_analysis(job_id, parsed)
                                    _sync_analysis_score(job_id, parsed)
                                except Exception:
                                    st.warning("Model returned unstructured output — displaying as text.")
                                    st.session_state[analysis_key] = raw_json
                                    save_job_fit_analysis(job_id, raw_json)
                                st.rerun()
                else:
                    st.info(
                        "Start here. This will analyze your fit for the role and ask you "
                        "clarifying questions before generating a resume."
                    )
                    if st.button(
                        "Analyze My Fit",
                        key=f"gen_analysis_{job_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        status_slot = st.empty()
                        status_slot.info("Generating…")
                        gen, err = analyze_fit_and_ask_questions(
                            title, company, description, master_resume
                        )
                        if err:
                            status_slot.error(err)
                        else:
                            raw_json = ""
                            char_count = 0
                            for chunk in gen:
                                raw_json += chunk
                                char_count += len(chunk)
                                status_slot.caption(f"Analyzing fit… {char_count} chars received")
                            status_slot.empty()
                            if not raw_json.strip():
                                st.error("AI returned an empty response. Check your API key and try again.")
                            else:
                                try:
                                    parsed = json.loads(raw_json)
                                    st.session_state[analysis_key] = parsed
                                    save_job_fit_analysis(job_id, parsed)
                                    _sync_analysis_score(job_id, parsed)
                                except Exception:
                                    st.warning("Model returned unstructured output — displaying as text.")
                                    st.session_state[analysis_key] = raw_json
                                    save_job_fit_analysis(job_id, raw_json)
                                st.rerun()

            # --- TAB 2: Tailored Resume ---
            with tab_resume:
                resume_key = f"resume_{job_id}"
                if resume_key not in st.session_state:
                    st.session_state[resume_key] = existing_resume if existing_resume.startswith("# ") else ""

                if st.session_state[resume_key]:
                    # --- Sync editor widget state (single source of truth = session state key) ---
                    editor_key = f"resume_editor_{job_id}"
                    pending_key = f"resume_pending_{job_id}"
                    if pending_key in st.session_state:
                        # AI produced a new version — push it into the widget state before render
                        st.session_state[editor_key] = st.session_state.pop(pending_key)
                    elif editor_key not in st.session_state:
                        # First time opening this resume — seed from saved value
                        st.session_state[editor_key] = st.session_state[resume_key]

                    edit_col, master_col = st.columns(2)

                    with edit_col:
                        st.markdown("**Edit Tailored Resume**")
                        # NOTE: no `value=` param — the key is the sole source of truth.
                        # Providing both `value` and `key` in Streamlit causes the value= to
                        # override session state on reruns, so manual edits are silently discarded.
                        st.text_area(
                            "Resume markdown",
                            height=480,
                            key=editor_key,
                            label_visibility="collapsed",
                        )
                        save_col, regen_col = st.columns(2)
                        with save_col:
                            if st.button("Save Edits", key=f"save_edits_{job_id}", use_container_width=True):
                                st.session_state[resume_key] = st.session_state[editor_key]
                                update_job_resume_summary(job_id, st.session_state[editor_key])
                                st.rerun()
                        with regen_col:
                            if st.button("Regenerate", key=f"regen_resume_{job_id}", use_container_width=True):
                                st.session_state[resume_key] = ""
                                del st.session_state[editor_key]
                                st.rerun()

                    with master_col:
                        st.markdown("**Master Resume** (reference — edit in sidebar)")
                        st.text_area(
                            "Master resume reference",
                            value=master_resume,
                            height=480,
                            disabled=True,
                            label_visibility="collapsed",
                            key=f"master_ref_{job_id}",
                        )

                    # Always read from the live widget state for preview and PDF
                    current_text = st.session_state.get(editor_key, st.session_state[resume_key])

                    st.markdown("**Preview**")
                    with st.container(height=400):
                        preview_text = re.sub(r"<</?(?:SIDEBAR|MAIN)>>\n?", "", current_text)
                        st.markdown(preview_text)

                    # PDF download — built from the same live current_text
                    try:
                        pdf_bytes = markdown_resume_to_pdf(current_text)
                        filename = f"Resume_{company.replace(' ', '_')}_{title.replace(' ', '_')}.pdf"
                        st.download_button(
                            "⬇️ Download Resume as PDF",
                            data=pdf_bytes,
                            file_name=filename,
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True,
                            key=f"dl_resume_{job_id}",
                        )
                    except Exception as e:
                        st.error(f"PDF generation error: {e}")

                    # --- AI Chat Editor ---
                    st.markdown("---")
                    chat_hdr_col, clear_col = st.columns([4, 1])
                    with chat_hdr_col:
                        st.markdown("**Ask AI to edit your resume**")
                        st.caption('e.g. "Make the summary more concise", "Move Python to the top of skills", "Add leadership experience from master resume"')

                    chat_history_key = f"chat_{job_id}"
                    if chat_history_key not in st.session_state:
                        st.session_state[chat_history_key] = []

                    with clear_col:
                        if st.session_state[chat_history_key]:
                            if st.button("Clear Chat", key=f"clear_chat_{job_id}"):
                                st.session_state[chat_history_key] = []
                                st.rerun()

                    # Display chat history
                    for msg in st.session_state[chat_history_key]:
                        with st.chat_message(msg["role"]):
                            st.markdown(msg["content"])

                    chat_input = st.chat_input("Tell the AI what to change...", key=f"chat_input_{job_id}")
                    if chat_input:
                        st.session_state[chat_history_key].append({"role": "user", "content": chat_input})
                        with st.chat_message("user"):
                            st.markdown(chat_input)

                        with st.chat_message("assistant"):
                            with st.spinner("Applying edits..."):
                                # Use the live editor state (reflects any unsaved manual edits too)
                                current = st.session_state.get(editor_key, st.session_state[resume_key])
                                gen, err = edit_resume_with_instruction(
                                    current, chat_input, description, master_resume
                                )
                            if err:
                                st.error(err)
                                st.session_state[chat_history_key].append({"role": "assistant", "content": f"Error: {err}"})
                            else:
                                updated = st.write_stream(gen)
                                st.session_state[resume_key] = updated
                                # Pending key pushes the update into the widget on next rerun
                                st.session_state[f"resume_pending_{job_id}"] = updated
                                update_job_resume_summary(job_id, updated)
                                st.session_state[chat_history_key].append({"role": "assistant", "content": "Done! Resume updated above."})
                                st.rerun()

                else:
                    analysis_key = f"analysis_{job_id}"
                    has_analysis = bool(st.session_state.get(analysis_key))

                    if not has_analysis:
                        st.info(
                            "Go to the **Fit Analysis** tab first to analyze your fit "
                            "and answer clarifying questions. This ensures a more accurate resume."
                        )
                    else:
                        st.info("Fit analysis complete. Click below to generate your tailored resume.")

                    if st.button(
                        "Generate Tailored Resume (1-page)",
                        key=f"gen_resume_{job_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        analysis_data = st.session_state.get(f"analysis_{job_id}")
                        if isinstance(analysis_data, dict):
                            questions = analysis_data.get("questions", [])
                            parts = []
                            for i, q in enumerate(questions):
                                q_text = q.get("question", f"Question {i + 1}")
                                selected = st.session_state.get(f"q_{job_id}_{i}", "")
                                if selected == "Other (type your own)":
                                    answer = st.session_state.get(f"q_other_{job_id}_{i}", "").strip()
                                else:
                                    answer = selected
                                if answer:
                                    parts.append(f"Q: {q_text}\nA: {answer}")
                            answers = "\n\n".join(parts)
                        else:
                            answers = st.session_state.get(f"answers_{job_id}", "")

                        with st.spinner("Generating 1-page tailored resume — this may take a few minutes..."):
                            gen, err = generate_tailored_resume(
                                title, company, description, master_resume, answers
                            )
                            if err:
                                st.error(err)
                            else:
                                result = st.write_stream(gen)
                                st.session_state[resume_key] = result
                                update_job_resume_summary(job_id, result)
                                st.rerun()

            # --- TAB 3: Cover Letter ---
            with tab_cover:
                cover_key = f"cover_{job_id}"
                if cover_key not in st.session_state:
                    st.session_state[cover_key] = ""

                if st.session_state[cover_key]:
                    st.markdown("**Preview:**")
                    st.markdown(st.session_state[cover_key])

                    try:
                        cover_pdf = markdown_resume_to_pdf(st.session_state[cover_key])
                        cover_filename = f"CoverLetter_{company.replace(' ', '_')}_{title.replace(' ', '_')}.pdf"
                        st.download_button(
                            "⬇️ Download Cover Letter as PDF",
                            data=cover_pdf,
                            file_name=cover_filename,
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True,
                            key=f"dl_cover_{job_id}",
                        )
                    except Exception as e:
                        st.error(f"PDF generation error: {e}")

                    if st.button("Regenerate Cover Letter", key=f"regen_cover_{job_id}"):
                        st.session_state[cover_key] = ""
                        st.rerun()
                else:
                    if st.button(
                        "Generate Cover Letter",
                        key=f"gen_cover_{job_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        with st.spinner("Generating cover letter..."):
                            gen, err = generate_cover_letter(
                                title, company, description, master_resume
                            )
                            if err:
                                st.error(err)
                            else:
                                result = st.write_stream(gen)
                                st.session_state[cover_key] = result
                                st.rerun()

        elif not has_resume:
            st.info("Add your master resume in the sidebar to enable AI tailoring.")
        elif not description:
            st.info("No job description available — AI tailoring needs a description to work with.")


def render_list_item(job):
    """Render job card with quick-action buttons inside the header area."""
    render_job_card(job)


def render_kanban_native(jobs_by_status):
    """Pure Streamlit Kanban — 4 columns, working Details and Apply buttons."""
    open_id = st.session_state.get("open_job_id", "")

    if open_id:
        back_col, _ = st.columns([1, 8])
        with back_col:
            if st.button("← Back to Board", key="back_kanban"):
                st.session_state["open_job_id"] = ""
                st.rerun()
        open_job = None
        for jobs_list in jobs_by_status.values():
            for j in jobs_list:
                if j.get("job_id") == open_id:
                    open_job = j
                    break
            if open_job:
                break
        if open_job:
            render_job_card(open_job)
        else:
            st.warning("Job not found.")
            st.session_state["open_job_id"] = ""
        return

    kb_cols = st.columns(4)
    for i, status in enumerate(STATUSES):
        with kb_cols[i]:
            jobs = jobs_by_status.get(status, [])
            emoji = STATUS_EMOJI.get(status, "")
            st.markdown(
                f'<div style="font-size:0.72rem;font-weight:600;text-transform:uppercase;'
                f'letter-spacing:0.06em;color:var(--muted);border-bottom:0.5px solid var(--line-strong);'
                f'padding-bottom:6px;margin-bottom:10px;">'
                f'{emoji} {status} &nbsp;'
                f'<span style="background:var(--accent-bg);color:var(--accent);'
                f'border:1px solid var(--accent-border);border-radius:100px;'
                f'padding:1px 8px;font-size:0.7rem;">{len(jobs)}</span></div>',
                unsafe_allow_html=True,
            )

            if not jobs:
                st.caption("No jobs here")

            for job in jobs:
                score = job.get("fit_score")
                if score is not None:
                    if score >= 80:
                        score_str, bar_color = f"🟢 {score}/100", "#22c55e"
                    elif score >= 60:
                        score_str, bar_color = f"🟡 {score}/100", "#d4c200"
                    elif score >= 40:
                        score_str, bar_color = f"🟠 {score}/100", "#d48000"
                    else:
                        score_str, bar_color = f"🔴 {score}/100", "#d44040"
                else:
                    score_str, bar_color = "⬜ Unscored", "var(--surface-3)"

                tags = []
                if job.get("visa_status") == "Sponsored":
                    tags.append("🟢")
                if job.get("remote"):
                    tags.append("🌐")
                if job.get("hybrid"):
                    tags.append("🔀")
                tag_str = " ".join(tags)

                st.markdown(
                    f'<div style="background:var(--surface-2);border:0.5px solid var(--line-strong);'
                    f'border-top:2px solid {bar_color};border-radius:8px;'
                    f'padding:10px 12px;margin-bottom:4px;">'
                    f'<div style="font-size:0.85rem;font-weight:600;color:var(--text);'
                    f'line-height:1.3;margin-bottom:2px;">'
                    f'{tag_str} {job.get("job_title") or "Untitled"}</div>'
                    f'<div style="font-size:0.75rem;color:var(--muted);margin-bottom:4px;">'
                    f'{job.get("company") or "Unknown"}</div>'
                    f'<div style="font-size:0.72rem;color:{bar_color};">{score_str}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                btn_a, btn_b = st.columns(2)
                with btn_a:
                    if st.button("Details →", key=f"kdet_{job['job_id']}", use_container_width=True):
                        st.session_state["open_job_id"] = job["job_id"]
                        st.rerun()
                with btn_b:
                    if job.get("apply_url"):
                        st.link_button("Apply", job["apply_url"], use_container_width=True, type="primary")
                st.markdown('<div style="height:2px"></div>', unsafe_allow_html=True)


# ===================== RENDER VIEWS =====================
if view_mode == "Kanban Board":
    if use_filtered:
        st.subheader(f"Search Results ({len(filtered_jobs)} jobs)")
        for job in filtered_jobs:
            render_list_item(job)
    else:
        jobs_data = get_all_jobs_by_status(sort_by=sort_by)
        if fit_score_filter != "All Scores":
            jobs_data = {s: _apply_fit_filter(lst, fit_score_filter) for s, lst in jobs_data.items()}
        render_kanban_native(jobs_data)

elif view_mode == "List View":
    if use_filtered:
        jobs_to_show = filtered_jobs
    else:
        jobs_to_show = _apply_fit_filter(get_all_jobs(sort_by=sort_by), fit_score_filter)

    st.subheader(f"All Jobs ({len(jobs_to_show)})")
    for job in jobs_to_show:
        render_list_item(job)
