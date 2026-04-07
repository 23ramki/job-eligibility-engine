import os
import uuid
import streamlit as st
from src.state_manager import (
    init_tracking_table, save_new_jobs,
    get_all_jobs_by_status, update_job_status, update_job_resume_summary,
    update_job_notes, search_jobs, get_job_stats, delete_job,
)
from src.llm_tailoring import (
    generate_tailored_resume, generate_cover_letter,
    analyze_fit_and_ask_questions, edit_resume_with_instruction,
)
from src.pdf_generator import markdown_resume_to_pdf
from src.job_scraper import scrape_and_extract

# --- Commented out: TheirStack API fetching (preserved for future use) ---
# from src.visa_filter import filter_eligible_jobs, _RED_PATTERN, _GREEN_PATTERN
# from src.notifier import send_discord_webhook
# from fetch_jobs import fetch_jobs_from_api, load_jobs_from_file

st.set_page_config(page_title="Job Eligibility CRM", page_icon="favicon.png", layout="wide")

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

# ===================== SIDEBAR =====================
with st.sidebar:
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
                    st.rerun()
                else:
                    st.error("Failed to save job.")

    # Manual fallback (collapsed by default)
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
        height=200,
        label_visibility="collapsed",
    )
    if st.button("Save Resume", use_container_width=True):
        os.makedirs("data", exist_ok=True)
        with open(resume_path, "w", encoding="utf-8") as f:
            f.write(edited_resume)
        master_resume = edited_resume
        has_resume = master_resume and master_resume.strip() != PLACEHOLDER
        st.success("Resume saved!")

    st.markdown("---")

    # --- Stats ---
    stats = get_job_stats()
    st.metric("Total Jobs", stats["total"])
    stat_cols = st.columns(2)
    with stat_cols[0]:
        st.metric("Sponsored", stats["sponsored"])
    with stat_cols[1]:
        st.metric("New", stats["by_status"].get("New", 0))


# ===================== MAIN CONTENT =====================
st.title("Job Eligibility CRM")

# --- Search & Filter Bar ---
filter_col1, filter_col2, filter_col3 = st.columns([3, 1, 1])
with filter_col1:
    search_query = st.text_input(
        "Search jobs",
        placeholder="Search by title, company, location, or keywords...",
    )
with filter_col2:
    status_filter = st.selectbox("Status", ["All", "New", "Applied", "Interviewing", "Rejected"])
with filter_col3:
    visa_filter = st.selectbox("Visa", ["All", "Sponsored", "Unknown/Neutral"])

# --- View Mode ---
view_mode = st.radio("View", ["Kanban Board", "List View"], horizontal=True, label_visibility="collapsed")

if search_query or status_filter != "All" or visa_filter != "All":
    filtered_jobs = search_jobs(search_query, status_filter, visa_filter)
    use_filtered = True
else:
    filtered_jobs = None
    use_filtered = False

STATUSES = ["New", "Applied", "Interviewing", "Rejected"]


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

    # Tags
    tags = []
    if visa == "Sponsored":
        tags.append("Sponsored")
    if remote:
        tags.append("Remote")
    if hybrid:
        tags.append("Hybrid")
    if seniority:
        tags.append(seniority.replace("_", " ").title())
    if emp_type:
        tags.append(emp_type.replace("_", " ").title())

    with st.expander(f"**{title}** — {company} | {location}"):
        if tags:
            st.caption(" | ".join(tags))

        # Key info
        info_cols = st.columns([1, 1, 1])
        with info_cols[0]:
            if date_posted:
                st.markdown(f"**Posted:** {date_posted}")
        with info_cols[1]:
            if salary:
                st.markdown(f"**Salary:** {salary}")
        with info_cols[2]:
            st.markdown(f"**Visa:** {visa}")

        # Apply links
        link_cols = st.columns(2)
        with link_cols[0]:
            if apply_url:
                st.link_button("Apply Now", apply_url, type="primary", use_container_width=True)
            else:
                st.info("No apply link available")
        with link_cols[1]:
            if source_url and source_url != apply_url:
                st.link_button("View Source", source_url, use_container_width=True)

        # Job description
        if description:
            st.markdown("**Job Description:**")
            with st.container(height=200):
                st.markdown(description[:5000])

        # Status & actions
        st.markdown("---")
        action_cols = st.columns([2, 1, 1])
        with action_cols[0]:
            idx = STATUSES.index(current_status) if current_status in STATUSES else 0
            new_status = st.selectbox("Move to", STATUSES, index=idx, key=f"sel_{job_id}")
            if new_status != current_status:
                update_job_status(job_id, new_status)
                st.rerun()
        with action_cols[1]:
            if st.button("Delete", key=f"del_{job_id}", type="secondary"):
                delete_job(job_id)
                st.rerun()

        # Notes
        current_notes = job.get("notes") or ""
        notes = st.text_area("Notes", value=current_notes, key=f"notes_{job_id}", height=80)
        if notes != current_notes:
            if st.button("Save Notes", key=f"savenotes_{job_id}"):
                update_job_notes(job_id, notes)
                st.success("Notes saved!")

        # ===================== AI RESUME TAILORING =====================
        if has_resume and description:
            st.markdown("---")
            st.subheader("AI Resume Tailoring")

            existing_resume = job.get("resume_summary") or ""

            tab_analysis, tab_resume, tab_cover = st.tabs([
                "1. Fit Analysis", "2. Tailored Resume", "3. Cover Letter"
            ])

            # --- TAB 1: Fit Analysis & Questions ---
            with tab_analysis:
                analysis_key = f"analysis_{job_id}"
                if analysis_key not in st.session_state:
                    st.session_state[analysis_key] = None

                analysis_data = st.session_state[analysis_key]

                if analysis_data:
                    if isinstance(analysis_data, dict):
                        # Structured response: render fit analysis then multiple-choice questions
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
                        # Fallback: raw markdown string from a failed JSON parse
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
                        # Collect current answers before overwriting the analysis
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

                        with st.spinner("Regenerating analysis with your answers..."):
                            result, err = analyze_fit_and_ask_questions(
                                title, company, description, master_resume, compiled_answers
                            )
                            if err:
                                st.error(err)
                            else:
                                st.session_state[analysis_key] = result
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
                        with st.spinner("Analyzing fit with Gemini..."):
                            result, err = analyze_fit_and_ask_questions(
                                title, company, description, master_resume
                            )
                            if err:
                                st.error(err)
                            else:
                                st.session_state[analysis_key] = result
                                st.rerun()

            # --- TAB 2: Tailored Resume ---
            with tab_resume:
                resume_key = f"resume_{job_id}"
                if resume_key not in st.session_state:
                    st.session_state[resume_key] = existing_resume if existing_resume.startswith("# ") else ""

                if st.session_state[resume_key]:
                    # Apply any pending AI edit BEFORE the widget is instantiated
                    pending_key = f"resume_pending_{job_id}"
                    if pending_key in st.session_state:
                        st.session_state[f"resume_editor_{job_id}"] = st.session_state.pop(pending_key)

                    edit_col, preview_col = st.columns(2)

                    with edit_col:
                        st.markdown("**Edit**")
                        edited_text = st.text_area(
                            "Resume markdown",
                            value=st.session_state[resume_key],
                            height=480,
                            key=f"resume_editor_{job_id}",
                            label_visibility="collapsed",
                        )
                        save_col, regen_col = st.columns(2)
                        with save_col:
                            if st.button("Save Edits", key=f"save_edits_{job_id}", use_container_width=True):
                                st.session_state[resume_key] = edited_text
                                update_job_resume_summary(job_id, edited_text)
                                st.success("Saved!")
                        with regen_col:
                            if st.button("Regenerate", key=f"regen_resume_{job_id}", use_container_width=True):
                                st.session_state[resume_key] = ""
                                st.rerun()

                    with preview_col:
                        st.markdown("**Preview**")
                        with st.container(height=480):
                            st.markdown(edited_text)

                    # PDF download
                    try:
                        pdf_bytes = markdown_resume_to_pdf(edited_text)
                        filename = f"Resume_{company.replace(' ', '_')}_{title.replace(' ', '_')}.pdf"
                        st.download_button(
                            "Download Resume as PDF",
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
                    st.markdown("**Ask Gemini to edit your resume**")
                    st.caption('e.g. "Make the summary more concise", "Move the Python skill to the top", "Add my leadership experience from the master resume"')

                    chat_history_key = f"chat_{job_id}"
                    if chat_history_key not in st.session_state:
                        st.session_state[chat_history_key] = []

                    # Display chat history
                    for msg in st.session_state[chat_history_key]:
                        with st.chat_message(msg["role"]):
                            st.markdown(msg["content"])

                    chat_input = st.chat_input("Tell Gemini what to change...", key=f"chat_input_{job_id}")
                    if chat_input:
                        st.session_state[chat_history_key].append({"role": "user", "content": chat_input})
                        with st.chat_message("user"):
                            st.markdown(chat_input)

                        with st.chat_message("assistant"):
                            with st.spinner("Applying edits..."):
                                current = st.session_state[resume_key]
                                updated, err = edit_resume_with_instruction(
                                    current, chat_input, description, master_resume
                                )
                            if err:
                                st.error(err)
                                st.session_state[chat_history_key].append({"role": "assistant", "content": f"Error: {err}"})
                            else:
                                st.session_state[resume_key] = updated
                                # Stage the update — applied to the widget key before next render
                                st.session_state[f"resume_pending_{job_id}"] = updated
                                update_job_resume_summary(job_id, updated)
                                st.markdown("Done! Resume updated above.")
                                st.session_state[chat_history_key].append({"role": "assistant", "content": "Done! Resume updated above."})
                                st.rerun()

                else:
                    # Check if user has done the fit analysis
                    analysis_key = f"analysis_{job_id}"
                    has_analysis = bool(st.session_state.get(analysis_key))

                    if not has_analysis:
                        st.info(
                            "Go to the **Fit Analysis** tab first to analyze your fit "
                            "and answer clarifying questions. This ensures a more accurate resume."
                        )

                    if st.button(
                        "Generate Tailored Resume (1-page)",
                        key=f"gen_resume_{job_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        # Collect answers from structured questions or fallback text area
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

                        with st.spinner("Generating 1-page tailored resume with Gemini..."):
                            result, err = generate_tailored_resume(
                                title, company, description, master_resume, answers
                            )
                            if err:
                                st.error(err)
                            else:
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
                            "Download Cover Letter as PDF",
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
                        with st.spinner("Generating cover letter with Gemini..."):
                            result, err = generate_cover_letter(
                                title, company, description, master_resume
                            )
                            if err:
                                st.error(err)
                            else:
                                st.session_state[cover_key] = result
                                st.rerun()

        elif not has_resume:
            st.info("Add your master resume in the sidebar to enable AI tailoring.")
        elif not description:
            st.info("No job description available — AI tailoring needs a description to work with.")


# ===================== RENDER VIEWS =====================
if view_mode == "Kanban Board":
    if use_filtered:
        st.subheader(f"Search Results ({len(filtered_jobs)} jobs)")
        for job in filtered_jobs:
            render_job_card(job)
    else:
        jobs_data = get_all_jobs_by_status()
        cols = st.columns(4)
        for i, status in enumerate(STATUSES):
            with cols[i]:
                status_jobs = jobs_data.get(status, [])
                st.subheader(f"{status} ({len(status_jobs)})")
                for job in status_jobs:
                    render_job_card(job)

elif view_mode == "List View":
    if use_filtered:
        jobs_to_show = filtered_jobs
    else:
        jobs_data = get_all_jobs_by_status()
        jobs_to_show = []
        for s in STATUSES:
            jobs_to_show.extend(jobs_data.get(s, []))

    st.subheader(f"All Jobs ({len(jobs_to_show)})")
    for job in jobs_to_show:
        render_job_card(job)
