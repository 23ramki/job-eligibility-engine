import re
import io
from fpdf import FPDF


class ResumePDF(FPDF):
    """Custom PDF class for generating clean, professional resumes."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=12)

    def header(self):
        pass

    def footer(self):
        pass


def markdown_resume_to_pdf(markdown_text, one_page=True):
    """
    Convert a markdown-formatted resume into a PDF.
    If one_page=True, only page 1 is kept (overflow is discarded).
    Returns the PDF as bytes (ready for st.download_button).
    """
    pdf = ResumePDF()
    pdf.add_page()
    pdf.set_margins(15, 12, 15)  # Tighter margins to maximize space

    lines = markdown_text.split("\n")
    i = 0

    while i < len(lines):
        if one_page and pdf.page > 1:
            break  # Stop rendering — already spilled to page 2

        line = lines[i].strip()

        if not line:
            pdf.ln(1.5)
            i += 1
            continue

        # H1 — Candidate Name
        if line.startswith("# ") and not line.startswith("## "):
            name = _strip_md(line[2:])
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 8, name, align="C", new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        # Contact line (right after name, contains | separators)
        if "|" in line and not line.startswith("#") and not line.startswith("-"):
            contact = _strip_md(line)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(0, 4, contact, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
            i += 1
            continue

        # H2 — Section headers
        if line.startswith("## "):
            section = _strip_md(line[3:])
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 5.5, section.upper(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(60, 60, 60)
            pdf.set_line_width(0.3)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(1.5)
            i += 1
            continue

        # H3 — Job title / subsection
        if line.startswith("### "):
            subtitle = _strip_md(line[4:])
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, subtitle, new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        # Date range line
        if _is_date_line(line):
            date_text = _strip_md(line)
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 4, date_text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.5)
            i += 1
            continue

        # Bullet points
        if line.startswith("- ") or line.startswith("* "):
            bullet_text = _strip_md(line[2:])
            pdf.set_font("Helvetica", "", 8)
            pdf.set_x(pdf.l_margin + 3)
            pdf.cell(3, 4, "-")
            available_w = pdf.w - pdf.get_x() - pdf.r_margin
            pdf.multi_cell(available_w, 4, bullet_text, new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue

        # Horizontal rule — skip
        if line.startswith("---"):
            i += 1
            continue

        # Regular text
        text = _strip_md(line)
        if text:
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(0, 4, text, new_x="LMARGIN", new_y="NEXT")

        i += 1

    # Enforce 1-page: delete any overflow pages
    if one_page and pdf.page > 1:
        while pdf.page > 1:
            del pdf.pages[pdf.page]
            pdf.page -= 1
    return bytes(pdf.output())


def _strip_md(text):
    """Remove common markdown formatting characters and sanitize for PDF."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)  # italic
    text = re.sub(r"__(.+?)__", r"\1", text)  # bold alt
    text = re.sub(r"_(.+?)_", r"\1", text)  # italic alt
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)  # links
    text = re.sub(r"`(.+?)`", r"\1", text)  # inline code
    text = _sanitize_unicode(text)
    return text.strip()


def _sanitize_unicode(text):
    """Replace Unicode characters that latin-1 can't encode."""
    replacements = {
        "\u2013": "-",   # en-dash
        "\u2014": "-",   # em-dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2026": "...", # ellipsis
        "\u2022": "-",   # bullet
        "\u00a0": " ",   # non-breaking space
        "\u200b": "",    # zero-width space
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    # Catch any remaining non-latin-1 characters
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    return text


def _is_date_line(line):
    """Heuristic: short line containing date-like patterns."""
    line = _strip_md(line)
    if len(line) > 80:
        return False
    date_patterns = [
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
        r"\b\d{4}\b",
        r"\bPresent\b",
    ]
    matches = sum(1 for p in date_patterns if re.search(p, line, re.IGNORECASE))
    return matches >= 2
