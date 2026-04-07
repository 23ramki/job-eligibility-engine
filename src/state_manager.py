import os
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


def _get_connection():
    """Return a SQLite connection to the local jobs database."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_tracking_table():
    """Create the jobs table if it doesn't exist."""
    ddl = """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id       TEXT PRIMARY KEY,
            job_title    TEXT,
            company      TEXT,
            location     TEXT,
            description  TEXT,
            visa_status  TEXT DEFAULT 'Unknown/Neutral',
            status       TEXT DEFAULT 'New',
            apply_url    TEXT,
            source_url   TEXT,
            salary_string TEXT,
            min_salary   REAL,
            max_salary   REAL,
            remote       INTEGER DEFAULT 0,
            hybrid       INTEGER DEFAULT 0,
            seniority    TEXT,
            employment_type TEXT,
            date_posted  TEXT,
            resume_summary TEXT,
            notes        TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    with _get_connection() as conn:
        conn.execute(ddl)

    _migrate_if_needed()


def _migrate_if_needed():
    """Add any columns that might be missing from an older schema."""
    new_columns = [
        ("location", "TEXT"),
        ("description", "TEXT"),
        ("source_url", "TEXT"),
        ("salary_string", "TEXT"),
        ("min_salary", "REAL"),
        ("max_salary", "REAL"),
        ("remote", "INTEGER DEFAULT 0"),
        ("hybrid", "INTEGER DEFAULT 0"),
        ("seniority", "TEXT"),
        ("employment_type", "TEXT"),
        ("date_posted", "TEXT"),
        ("notes", "TEXT"),
    ]
    with _get_connection() as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        for col_name, col_type in new_columns:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")


def get_all_jobs_by_status():
    """Fetch all jobs grouped by status for the Kanban board."""
    query = "SELECT * FROM jobs ORDER BY created_at DESC"
    result = {"New": [], "Applied": [], "Interviewing": [], "Rejected": []}

    with _get_connection() as conn:
        rows = conn.execute(query).fetchall()
        for row in rows:
            job = dict(row)
            status = job.get("status") or "New"
            if status not in result:
                result[status] = []
            result[status].append(job)
    return result


def get_job_by_id(job_id):
    """Fetch a single job by its ID."""
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def update_job_status(job_id, new_status):
    """Update the kanban status of a job."""
    with _get_connection() as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE job_id = ?", (new_status, job_id))


def update_job_resume_summary(job_id, summary):
    """Save AI-generated tailored summary."""
    with _get_connection() as conn:
        conn.execute("UPDATE jobs SET resume_summary = ? WHERE job_id = ?", (summary, job_id))


def update_job_notes(job_id, notes):
    """Save user notes for a job."""
    with _get_connection() as conn:
        conn.execute("UPDATE jobs SET notes = ? WHERE job_id = ?", (notes, job_id))


def get_seen_job_ids():
    """Return a set of all job_id strings already in the database."""
    with _get_connection() as conn:
        rows = conn.execute("SELECT job_id FROM jobs").fetchall()
        return {row["job_id"] for row in rows}


def save_new_jobs(new_jobs_list):
    """Insert a list of job dicts into the database."""
    if not new_jobs_list:
        return 0

    insert_sql = """
        INSERT OR IGNORE INTO jobs
            (job_id, job_title, company, location, description, visa_status,
             apply_url, source_url, salary_string, min_salary, max_salary,
             remote, hybrid, seniority, employment_type, date_posted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    rows = []
    for job in new_jobs_list:
        raw_id = job.get("id")
        if raw_id is None:
            continue

        company = job.get("company_name") or job.get("company", "")
        apply_url = job.get("url") or job.get("apply_url") or job.get("final_url") or ""
        source_url = job.get("source_url") or ""
        employment_types = job.get("employment_statuses") or []
        emp_type = ", ".join(employment_types) if isinstance(employment_types, list) else str(employment_types)

        rows.append((
            str(raw_id),
            job.get("job_title", ""),
            company,
            job.get("location") or job.get("short_location", ""),
            job.get("description", ""),
            job.get("visa_status", "Unknown/Neutral"),
            apply_url,
            source_url,
            job.get("salary_string", ""),
            job.get("min_annual_salary"),
            job.get("max_annual_salary"),
            1 if job.get("remote") else 0,
            1 if job.get("hybrid") else 0,
            job.get("seniority", ""),
            emp_type,
            job.get("date_posted", ""),
        ))

    if not rows:
        return 0

    with _get_connection() as conn:
        conn.executemany(insert_sql, rows)

    return len(rows)


def search_jobs(query_text, status_filter=None, visa_filter=None):
    """Search jobs by keyword across title, company, description, location."""
    conditions = []
    params = []

    if query_text:
        conditions.append(
            "(job_title LIKE ? OR company LIKE ? OR description LIKE ? OR location LIKE ?)"
        )
        like = f"%{query_text}%"
        params.extend([like, like, like, like])

    if status_filter and status_filter != "All":
        conditions.append("status = ?")
        params.append(status_filter)

    if visa_filter and visa_filter != "All":
        conditions.append("visa_status = ?")
        params.append(visa_filter)

    where = " AND ".join(conditions) if conditions else "1=1"
    query = f"SELECT * FROM jobs WHERE {where} ORDER BY created_at DESC"

    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_job_stats():
    """Return summary stats for the dashboard."""
    with _get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        by_status = {}
        for row in conn.execute("SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status").fetchall():
            by_status[row["status"]] = row["cnt"]
        sponsored = conn.execute("SELECT COUNT(*) FROM jobs WHERE visa_status = 'Sponsored'").fetchone()[0]
        return {"total": total, "by_status": by_status, "sponsored": sponsored}


def delete_job(job_id):
    """Remove a job from the database."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
