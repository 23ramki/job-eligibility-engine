import json
import re
from src.ollama_client import generate, generate_stream, GEMINI_MODEL


# ── Token-reduction helpers ───────────────────────────────────────────────────

_REQUIREMENTS_HEADERS = re.compile(
    r"(?im)^.*?(requirements?|qualifications?|what you.ll need|what we.re looking for"
    r"|skills?\s+required|minimum qualifications?|preferred qualifications?"
    r"|basic qualifications?|must.have|you.ll bring|what you bring).*$"
)
_BOILERPLATE_HEADERS = re.compile(
    r"(?im)^.*?(equal opportunity|eeo|diversity|benefits?|what we offer"
    r"|perks?|compensation|salary range|about the company|who we are"
    r"|our mission|our values|why join).*$"
)


def _extract_jd_requirements(jd_text: str, max_chars: int = 1500) -> str:
    """Return the requirements-focused portion of a job description.

    Strategy:
    1. Find the first requirements section header and take from there.
    2. If found, also chop off any trailing boilerplate (benefits, EEO).
    3. Fall back to skipping the first 15% (company overview) if no header found.
    """
    req_match = _REQUIREMENTS_HEADERS.search(jd_text)
    if req_match:
        start = req_match.start()
        candidate = jd_text[start:]
        # Chop at the first boilerplate section that comes after requirements
        blurb_match = _BOILERPLATE_HEADERS.search(candidate)
        if blurb_match and blurb_match.start() > 200:
            candidate = candidate[:blurb_match.start()]
        return candidate[:max_chars]
    # Fallback: skip company intro, take middle section
    skip = max(0, len(jd_text) // 7)
    return jd_text[skip:skip + max_chars]


_STOP_SECTIONS = re.compile(
    r"(?im)^\[SECTION:\s*AUTHOR\s*TONE|^\[SECTION:\s*ADD\s*NEW|"
    r"^%%%\s*Instructions\s*for|^%%%\s*END\s*ADD|^%%%\s*EXAMPLE"
)


def _prepare_resume_for_generation(resume_text: str, max_chars: int = 9000) -> str:
    """Strip instruction/template overhead then return up to max_chars of real resume content.

    Sections removed: AUTHOR TONE & VOICE RULES, ADD NEW CONTENT template, %%% comments.
    Everything else (contact, summary, skills, experience, education, certs, projects)
    is kept. Truncates at the last clean section boundary if still over max_chars.
    """
    stop = _STOP_SECTIONS.search(resume_text)
    clean = resume_text[: stop.start()].rstrip() if stop else resume_text

    if len(clean) <= max_chars:
        return clean

    candidate = clean[:max_chars]
    # Prefer cutting at a section/job boundary rather than mid-sentence
    last_break = max(
        candidate.rfind("\n["),
        candidate.rfind("\n##"),
    )
    if last_break > int(max_chars * 0.6):
        return candidate[:last_break].rstrip()
    return candidate


def _compress_resume_for_scoring(resume_text: str, max_chars: int = 1000) -> str:
    """Extract the scoring-relevant parts of a resume for lightweight fit calls.

    Supports both standard markdown (## Skills) and custom [SECTION:] formats.
    Pulls: Skills + first chunk of Experience + Education.
    Falls back to first `max_chars` chars if no headers found.
    """
    # Match both "## Skills" (markdown) and "[SECTION: SKILLS]" (custom format)
    skills_m = re.search(
        r"(?im)^#{1,3}\s*skills?|^\[SKILL_CATEGORY|^\[SECTION:\s*SKILLS?\]",
        resume_text,
    )
    exp_m = re.search(
        r"(?im)^#{1,3}\s*experience|^\[SECTION:\s*WORK\s*EXPERIENCE\]|^\[JOB\]",
        resume_text,
    )
    edu_m = re.search(
        r"(?im)^#{1,3}\s*education|^\[SECTION:\s*EDUCATION\]",
        resume_text,
    )

    parts: list[str] = []

    if skills_m:
        end = exp_m.start() if exp_m else (edu_m.start() if edu_m else len(resume_text))
        parts.append(resume_text[skills_m.start():end].strip()[:350])

    if exp_m:
        end = edu_m.start() if edu_m else len(resume_text)
        parts.append(resume_text[exp_m.start():end].strip()[:500])

    if edu_m:
        parts.append(resume_text[edu_m.start():].strip()[:200])

    if parts:
        return "\n\n".join(parts)[:max_chars]

    return resume_text[:max_chars]


def quick_fit_score(job_title, company, job_description, master_resume_text):
    """
    Fast, lightweight fit score (0-100) for sorting and filtering.
    Uses non-streaming generate() via Gemini API.
    Returns ({"score": int, "label": str, "reason": str}, error_message).
    """
    prompt = f"""You are a strict, unbiased recruiter scoring resume-to-job fit. Be critical.

CRITICAL CALIBRATION RULES — you MUST follow these:
- Typical score is 40-65. Most candidates are Partial or Good Fit.
- Only give 70+ if the candidate's background directly matches the core requirements.
- Only give 80+ if skills, seniority level, AND domain experience all align closely.
- Give below 40 if there are major skill gaps or the role is a different domain entirely.
- DO NOT inflate scores. A generous score is a useless score.
- Seniority gap for ANALYST applying to SENIOR/MANAGER: cap at 60.
  EXCEPTION: A relevant Master's degree + industry certifications can raise this cap to 70 if domain skills align.
- Missing the primary technical skill listed in the job title caps the score at 50.

Schema: {{"score": <integer 0-100>, "label": "<Strong Match|Good Fit|Partial Fit|Weak Fit>", "reason": "<one concise sentence stating the single biggest alignment or gap>"}}

Labels:
- 80-100: Strong Match
- 60-79: Good Fit
- 40-59: Partial Fit
- 0-39: Weak Fit

JOB: {job_title} at {company}
REQUIREMENTS:
{_extract_jd_requirements(job_description, 1200)}

CANDIDATE:
{_compress_resume_for_scoring(master_resume_text, 1000)}

Return ONLY the JSON object, nothing else."""

    result, err = generate(prompt, json_mode=True, temperature=0.1, num_predict=150)
    if err:
        return None, err
    try:
        data = json.loads(result)
        score = max(0, min(100, int(data.get("score", 0))))
        label = data.get("label", "Unscored")
        reason = data.get("reason", "")
        return {"score": score, "label": label, "reason": reason}, None
    except Exception:
        return None, "Could not parse fit score response"


def analyze_fit_and_ask_questions(job_title, company, job_description, master_resume_text, user_answers=""):
    """
    Analyze fit and surface structured clarifying questions.
    If user_answers are provided (from a previous round), incorporates them to produce
    an augmented analysis with a revised fit score and refined follow-up questions.

    Returns (result, error_message) where result is either:
      - A dict with keys 'fit_analysis' (markdown str) and 'questions' (list of {question, options})
      - A raw markdown string (fallback if JSON parsing fails)
    """
    if user_answers:
        answers_block = f"""
--- CANDIDATE'S ANSWERS TO CLARIFYING QUESTIONS ---
{user_answers}

These are the candidate's own answers to the questions from the previous analysis round.
Use them to:
  1. Revise the Fit Score if the answers reveal stronger alignment than the resume alone showed.
  2. Update Strong Matches — promote items clarified by the answers.
  3. Update Gaps — mark resolved gaps as resolved and remove them, or downgrade their severity.
  4. Generate NEW follow-up questions only for areas that are still ambiguous after the answers.
     If all ambiguities are resolved, return an empty questions array.
---
"""
    else:
        answers_block = ""

    task_description = (
        "Incorporate the candidate's answers above into a REVISED, augmented analysis."
        if user_answers else
        "Perform an initial fit analysis and generate clarifying questions."
    )

    prompt = f"""You are a career coach reviewing a candidate's fit for a specific job.

TASK: {task_description}

Return ONLY valid JSON with NO extra text before or after it. Use this exact schema:
{{
  "fit_analysis": "### Fit Score\\nX/10 — ...\\n\\n### Strong Matches\\n- ...\\n\\n### Gaps\\n- ...",
  "questions": [
    {{
      "question": "Specific question about the candidate's experience?",
      "options": [
        "Option A grounded in the resume",
        "Option B grounded in the resume",
        "Option C grounded in the resume"
      ]
    }}
  ]
}}

RULES for fit_analysis (a single markdown string):
- ### Fit Score: X/10 with a brief honest rationale
- ### Strong Matches: 3-5 bullet points of direct alignment (include clarifications from answers if provided)
- ### Gaps: remaining gaps only — omit anything resolved by the candidate's answers
- Base ALL analysis strictly on what is in the master resume and the candidate's answers
{answers_block}
RULES for questions:
- Ask exactly 2 to 4 specific clarifying questions about areas STILL ambiguous.
- CRITICAL SHUTOFF: DO NOT ask more than 4 questions. You must stop generating after the 4th question.
- Do NOT repeat the same questions.
- If all ambiguities are resolved, return an empty array: "questions": []
- For each question provide exactly 3-4 plausible answer options grounded in the resume.

---

TARGET JOB:
Title: {job_title}
Company: {company}

Job Description:
{_extract_jd_requirements(job_description, 2500)}

---

MASTER RESUME:
{_prepare_resume_for_generation(master_resume_text, max_chars=7000)}"""

    gen, err = generate_stream(prompt, json_mode=True, temperature=0.2, num_predict=1800, force_gemini=True)
    if err:
        return None, err

    return gen, None


def generate_tailored_resume(job_title, company, job_description, master_resume_text, user_answers=""):
    """
    Generate a one-page tailored resume using the PAR framework.
    Layout: two-column (sidebar 25% left / main 75% right) via <<SIDEBAR>> markers.
    ZERO fabrication — only sourced from master resume and candidate answers.
    Returns (resume_markdown, error_message).
    """
    answers_section = ""
    if user_answers:
        answers_section = f"""
--- CANDIDATE'S ANSWERS TO CLARIFYING QUESTIONS ---
{user_answers}

Incorporate these verbatim as first-person facts. No embellishment or inference beyond what is stated.
---
"""

    prompt = f"""You are an elite resume strategist. Produce a dense ONE-PAGE single-column resume for {company}.

COMPLETION MANDATE: Output ALL sections before stopping — # Name → ## Summary → ## Skills → ## Experience → ## Projects → ## Education → ## Certifications. Shorten bullets to fit, but NEVER omit Education or Certifications.

RULE 1 — ZERO FABRICATION & CORRECT ATTRIBUTION:
Every fact, metric, skill, title, company, and date MUST exist in the MASTER RESUME or CANDIDATE ANSWERS. Never invent anything.
PROPER NOUNS ARE VERBATIM — copy these character-for-character from the master resume, no exceptions:
  - University/institution names (NEVER substitute a more prestigious school)
  - Company names (exact spelling and formatting)
  - Job titles (exact wording — NEVER inflate to match the job being applied for)
  - Dates (exact months and years)
Each achievement belongs to the EXACT role where it happened. NEVER write "for a previous company", "at a former employer", "in a prior role", or any phrase that admits cross-company confusion. If work happened at Company B, it goes under Company B's role header — never under Company A's bullets.
SELF-CHECK: Before outputting, verify every university name, company name, and job title in your output matches the master resume word-for-word. Correct any that differ.
{answers_section}
RULE 2 — PAR BULLETS (Experience & Projects):
Formula: [Strong Past-tense Verb] + [Context + specific Tool] → [**Bolded metric**]
- End each bullet with a **bolded** metric (%, $, count, time, or scope).
- Max 2 lines per bullet. Each bullet UNIQUE — never repeat an accomplishment in different words.
- Weave in one **bolded** JD keyword per bullet.
- Most recent role: 4 bullets. All others: 3 bullets.
- BANNED weak openers (for Analyst/Specialist/Manager level): Assisted, Helped, Supported, Coordinated, Participated, Contributed. Use instead: Built, Designed, Deployed, Led, Drove, Automated, Architected, Engineered, Scaled, Modeled, Launched, Directed, Negotiated.

RULE 3 — SECTIONS:
SUMMARY (exactly 3 lines):
  Line 1: degree + years of experience + domain + top 2–3 JD tools/keywords.
  Line 2: ONE **bolded** metric-led result — MUST start with a bolded number or impact (e.g., **Drove 20% conversion uplift** or **Cut costs $500K across 70+ sites**). Must NOT be a responsibility description. Must NOT contain "for a previous company" or any attribution hedge.
  Line 3: direct value proposition naming {company} explicitly. No clichés.
SKILLS: 2 categories per line using |. JD-matching skills first. Only from master resume.
  **Analytics & BI:** · · |  **Data & Cloud:** · ·
  **Methods:** · · |  **CRM & Tools:** · ·
EXPERIENCE: All roles, reverse-chron. ### Title | Company | Mon Year – Mon Year
PROJECTS: Up to 2. ### Name | tech · tech
  CRITICAL: Projects MUST describe work NOT already in Experience bullets. Do NOT rephrase or summarize Experience bullets as projects. Projects = academic, personal, open-source, or clearly named deliverables distinct from day-to-day job duties. If the master resume has no such distinct projects, include only 1 project or omit this section entirely.
EDUCATION (REQUIRED): Both degrees — **Degree, Field** | Institution | Dates. No GPA < 3.5.
CERTIFICATIONS (REQUIRED): **Certifications:** Cert1 · Cert2

EXCLUDE: No address/city/age, no Objective, no "References available", no passive phrases, no fabrications.
UNIQUENESS CHECK: Before finalizing, verify no sentence in Projects paraphrases a sentence in Experience. Every line must add information not already stated elsewhere in the resume.

TARGET JOB: {job_title} at {company}

JOB REQUIREMENTS:
{_extract_jd_requirements(job_description, 3000)}

MASTER RESUME:
{master_resume_text}

Output ONLY the resume. Start with # [Full Name]. Output is INCOMPLETE if ## Certifications is missing."""

    gen, err = generate_stream(prompt, temperature=0.25, num_predict=4096, force_gemini=True)
    if err:
        return None, err
    return gen, None


def edit_resume_with_instruction(current_resume, instruction, job_description, master_resume_text):
    """
    Apply a natural-language edit instruction to an existing tailored resume.
    Returns (updated_resume_markdown, error_message).
    Strict no-fabrication rules apply — only rearrange or rephrase real content,
    or incorporate new details from the master resume.
    """
    prompt = f"""You are an expert resume editor. The user wants to modify their tailored resume.

ABSOLUTE RULES — same as when the resume was first generated:
1. ZERO FABRICATION: Every fact, skill, number, date, company, and title must come from
   the MASTER RESUME or already exist in the CURRENT RESUME. Do not invent anything.
2. ONE PAGE: Keep the resume fitting on a single page — be concise.
3. Apply ONLY what the user's instruction asks for. Do not make other changes.

USER'S EDIT INSTRUCTION:
{instruction}

---

CURRENT RESUME (markdown):
{current_resume}

---

MASTER RESUME (source of truth for any new facts):
{master_resume_text}

---

JOB DESCRIPTION (for context):
{_extract_jd_requirements(job_description, 1500)}

---

Return ONLY the updated resume in the same markdown format. No commentary, no preamble."""

    gen, err = generate_stream(prompt, temperature=0.2, num_predict=3000, force_gemini=True)
    if err:
        return None, err
    return gen, None


def generate_cover_letter(job_title, company, job_description, master_resume_text):
    """Generate a tailored cover letter with the same no-fabrication guardrails."""
    prompt = f"""You are an expert career coach. Write a concise, compelling cover letter.

RULES:
- Under 250 words
- Open with a strong hook, not "I am writing to apply..."
- Connect 2-3 specific experiences from the resume to job requirements
- ONLY reference real experience from the master resume — do not fabricate
- Show genuine interest in the company
- Close with a clear call to action
- Professional but warm tone

TARGET JOB:
Title: {job_title}
Company: {company}

Job Description:
{_extract_jd_requirements(job_description, 2000)}

CANDIDATE RESUME:
{master_resume_text[:3000]}

Write the cover letter now. Output ONLY the letter text — no preamble or commentary."""

    gen, err = generate_stream(prompt, temperature=0.5, num_predict=500, force_gemini=True)
    if err:
        return None, err
    return gen, None
