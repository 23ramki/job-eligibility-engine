import os
import json
import re
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Model to use for all Gemini calls.
# gemini-2.5-flash  — recommended (thinking model, best quality/cost balance, requires billing)
# gemini-2.5-pro    — highest quality, higher cost
# gemini-2.0-flash  — 1,500 free req/day, weaker reasoning
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _get_client():
    """Return an authenticated Gemini client, or None with an error message."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None, "GEMINI_API_KEY is not set in your .env file."
    return genai.Client(api_key=api_key), None


def analyze_fit_and_ask_questions(job_title, company, job_description, master_resume_text, user_answers=""):
    """
    Analyze fit and surface structured clarifying questions.
    If user_answers are provided (from a previous round), incorporates them to produce
    an augmented analysis with a revised fit score and refined follow-up questions.

    Returns (result, error_message) where result is either:
      - A dict with keys 'fit_analysis' (markdown str) and 'questions' (list of {question, options})
      - A raw markdown string (fallback if JSON parsing fails)
    """
    client, err = _get_client()
    if err:
        return None, err

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
- Ask 2-4 specific clarifying questions about areas STILL ambiguous after reviewing all available info
- If all ambiguities are resolved by the answers, return an empty array: "questions": []
- For each question provide exactly 3-4 plausible answer options grounded in the resume and job requirements
- Do NOT include a generic "Other" option — that will be injected automatically by the UI
- Questions must help write a better resume, not be generic

---

TARGET JOB:
Title: {job_title}
Company: {company}

Job Description:
{job_description[:4000]}

---

MASTER RESUME:
{master_resume_text}"""

    response = None
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        text = response.text.strip()
        # Strip markdown code fences if present
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1)
        data = json.loads(text)
        return data, None
    except json.JSONDecodeError:
        # Return raw text as fallback so the UI can still show something
        return response.text if response else None, None
    except Exception as e:
        if response is not None:
            return response.text, None
        return None, f"Gemini API error: {e}"


def generate_tailored_resume(job_title, company, job_description, master_resume_text, user_answers=""):
    """
    Generate a full tailored resume with strict guardrails:
    - ONE PAGE maximum — concise, no filler
    - ZERO fabrication — only use experience, skills, and numbers from the master resume
    - If user provided answers to clarifying questions, incorporate them

    Returns (resume_markdown, error_message).
    """
    client, err = _get_client()
    if err:
        return None, err

    answers_section = ""
    if user_answers:
        answers_section = f"""
--- CANDIDATE'S ANSWERS TO CLARIFYING QUESTIONS ---
{user_answers}

Treat these answers as first-person factual statements from the candidate.
Incorporate them exactly as provided — do not embellish or infer beyond what is stated.
---
"""

    prompt = f"""You are a senior technical recruiter and resume strategist with 15 years of experience
placing candidates at top-tier companies. Your task is to produce a ONE-PAGE, ATS-optimized,
recruiter-ready tailored resume. You will be judged on four pillars — violating any one fails the task.

════════════════════════════════════════════════════════
PILLAR 1 — ZERO FABRICATION (HIGHEST PRIORITY)
════════════════════════════════════════════════════════
Your ONLY sources of truth are:
  (a) The MASTER RESUME provided below
  (b) The candidate's ANSWERS TO CLARIFYING QUESTIONS (if provided)

You are STRICTLY FORBIDDEN from:
- Inventing, estimating, or inferring any metric, percentage, or number not explicitly stated
- Adding any skill, tool, language, framework, or technology not listed in (a) or (b)
- Claiming experience with anything not mentioned — including tools implied by the job description
- Upgrading job titles, inflating responsibilities, or fabricating achievements
- Adding certifications, degrees, or projects not present in the source material

If the job description demands a skill the candidate does not have → OMIT IT ENTIRELY.
Never write a placeholder like "experience with X preferred" or hint at a missing skill.
Silence is always better than invention.

════════════════════════════════════════════════════════
PILLAR 2 — ATS OPTIMIZATION
════════════════════════════════════════════════════════
- Use EXACT section headers for ATS parsing: "Experience", "Skills", "Education", "Certifications"
- Integrate high-value keywords from the job description VERBATIM into bullet points — but ONLY
  where a genuine, truthful match exists in the master resume. Never keyword-stuff.
- Avoid tables, columns, graphics, icons, or non-standard characters that break ATS parsers.
- Use a clean hierarchy: H1 for name, H2 for sections, H3 for job titles.
- Spell out acronyms on first use if they appear in the job description (e.g. "CI/CD pipelines").

════════════════════════════════════════════════════════
PILLAR 3 — RECRUITER APPEAL (ACTION-ORIENTED & QUANTIFIABLE)
════════════════════════════════════════════════════════
Every bullet point MUST:
1. Open with a strong past-tense action verb (Led, Built, Reduced, Designed, Shipped, etc.)
2. Follow the XYZ structure where data exists:
   "Accomplished [X] as measured by [Y], by doing [Z]"
   Example: "Reduced API response time by 40% by refactoring database query layer to use indexed reads"
3. If no metric exists in the source material, use impact-first language instead of inventing one:
   "Architected the end-to-end data pipeline that became the team's core ETL workflow"
- Front-load bullets by relevance to the job description — most impactful and relevant first.
- Cut any bullet with no relevance to the target role to preserve space.
- The professional summary must be 2 punchy sentences: who the candidate is + what they bring
  to THIS specific role. No fluff. No "results-driven professional."

════════════════════════════════════════════════════════
PILLAR 4 — AUTHENTICITY (MIRROR THE CANDIDATE'S VOICE)
════════════════════════════════════════════════════════
Before writing a single word, analyze the master resume for:
- Sentence length and rhythm (short and punchy vs. detailed and descriptive)
- Vocabulary register (technical jargon level, industry-specific terms they use)
- Preferred phrasing patterns (e.g., do they write "built" or "developed"? "led" or "managed"?)
- Level of formality

Then write the entire output in that SAME voice. The resume must read like the candidate wrote it
on their best day — not like a generic AI. Strip out corporate buzzwords ("synergize", "leverage",
"passionate about") unless those exact words appear in the master resume.

════════════════════════════════════════════════════════
ONE-PAGE CONSTRAINT
════════════════════════════════════════════════════════
The output must fit on a single printed page. Enforce this by:
- Professional Summary: 2 sentences maximum
- Experience: 2-3 most relevant roles, 3-4 bullets each (cut less relevant roles entirely)
- Skills: one compact line per category, most relevant categories first
- Education: degree, institution, year — nothing more unless directly relevant
- Certifications: comma-separated single line, most relevant first
- Projects: include only if directly relevant AND space permits (1 entry max, 2 bullets max)
{answers_section}
════════════════════════════════════════════════════════
OUTPUT FORMAT — use exactly these markdown headers, no deviations
════════════════════════════════════════════════════════
# [Full Name]
[email] | [phone] | [LinkedIn] | [Portfolio/GitHub if present]

## Summary
[2 sentences — tailored to this role, built from real experience, in the candidate's voice]

## Skills
[Category]: [skill1, skill2, skill3 — ordered by relevance to job description]

## Experience
### [Exact Job Title from resume] | [Company]
[Start Date] – [End Date]
- [Action verb] [achievement using XYZ where data exists — job-description keyword integrated truthfully]
- [Action verb] [achievement]
- [Action verb] [achievement]

## Education
### [Degree] | [Institution]
[Graduation Year or Date Range]

## Certifications
[Cert 1], [Cert 2], [Cert 3]

---

TARGET JOB:
Title: {job_title}
Company: {company}

Job Description:
{job_description[:4000]}

---

MASTER RESUME:
{master_resume_text}

---

Produce the ONE-PAGE tailored resume now.
Final self-check before outputting — ask yourself:
  ✓ Does every fact trace back to the master resume or candidate answers?
  ✓ Does every bullet start with an action verb?
  ✓ Are job description keywords integrated only where truthful?
  ✓ Does the voice match the candidate's original writing style?
  ✓ Will this fit on one printed page?
If any answer is no, fix it before outputting."""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text, None
    except Exception as e:
        return None, f"Gemini API error: {e}"


def edit_resume_with_instruction(current_resume, instruction, job_description, master_resume_text):
    """
    Apply a natural-language edit instruction to an existing tailored resume.
    Returns (updated_resume_markdown, error_message).
    Strict no-fabrication rules apply — only rearrange or rephrase real content,
    or incorporate new details from the master resume.
    """
    client, err = _get_client()
    if err:
        return None, err

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
{job_description[:2000]}

---

Return ONLY the updated resume in the same markdown format. No commentary, no preamble."""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text, None
    except Exception as e:
        return None, f"Gemini API error: {e}"


def generate_cover_letter(job_title, company, job_description, master_resume_text):
    """Generate a tailored cover letter with the same no-fabrication guardrails."""
    client, err = _get_client()
    if err:
        return None, err

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
{job_description[:3000]}

CANDIDATE RESUME:
{master_resume_text}

Write the cover letter now."""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text, None
    except Exception as e:
        return None, f"Gemini API error: {e}"
