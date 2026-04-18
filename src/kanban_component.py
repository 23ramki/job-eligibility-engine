"""
Drag-and-drop Kanban board custom Streamlit component.

Returns a dict or None:
  {"action": "move",    "job_id": str, "from_status": str, "to_status": str}
  {"action": "details", "job_id": str}
"""
from pathlib import Path
import streamlit.components.v1 as components

_FRONTEND_DIR = Path(__file__).parent / "kanban_frontend"

_kanban_component = components.declare_component(
    "kanban_board",
    path=str(_FRONTEND_DIR),
)


def kanban_board(jobs_by_status, statuses, status_emojis, theme="dark", key=None):
    """
    Render a drag-and-drop Kanban board.

    Parameters
    ----------
    jobs_by_status : dict[str, list[dict]]
        Jobs grouped by status key (already sorted by fit_score).
    statuses : list[str]
        Ordered list of column names.
    status_emojis : dict[str, str]
        Emoji prefix per status.
    theme : "dark" | "light"
    key : str, optional
        Streamlit widget key for stable identity across reruns.

    Returns
    -------
    dict or None
        None on first render or no interaction yet.
    """
    slim = {}
    for status, jobs in jobs_by_status.items():
        slim[status] = [
            {
                "job_id":      j.get("job_id", ""),
                "job_title":   j.get("job_title", ""),
                "company":     j.get("company", ""),
                "location":    j.get("location") or "",
                "visa_status": j.get("visa_status") or "",
                "remote":      bool(j.get("remote")),
                "hybrid":      bool(j.get("hybrid")),
                "fit_score":   j.get("fit_score"),
                "fit_label":   j.get("fit_label") or "",
                "fit_reason":  j.get("fit_reason") or "",
            }
            for j in jobs
        ]

    return _kanban_component(
        jobs_by_status=slim,
        statuses=statuses,
        status_emojis=status_emojis,
        theme=theme,
        key=key,
        default=None,
    )
