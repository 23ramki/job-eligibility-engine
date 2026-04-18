import re
from fpdf import FPDF

# ---------------------------------------------------------------------------
# Layout constants (mm, A4)
# ---------------------------------------------------------------------------
_PAGE_W    = 210
_L_MARGIN  = 12
_R_MARGIN  = 12
_T_MARGIN  = 10
_LEFT_COL_W = 58          # ~31 % of usable width
_COL_GAP   = 4
_RIGHT_COL_X = _L_MARGIN + _LEFT_COL_W + _COL_GAP   # 62 mm
_RIGHT_COL_W = _PAGE_W - _R_MARGIN - _RIGHT_COL_X   # ~136 mm


class ResumePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=12)

    def header(self):
        pass

    def footer(self):
        pass


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def markdown_resume_to_pdf(markdown_text, one_page=True):
    """
    Convert a markdown resume to PDF.
    If the text contains <<SIDEBAR>> / <<MAIN>> markers, renders a two-column layout
    (left 25 % sidebar | right 75 % main).  Otherwise falls back to single-column.
    Returns PDF as bytes.
    """
    if "<<SIDEBAR>>" in markdown_text and "<<MAIN>>" in markdown_text:
        return _two_column_pdf(markdown_text, one_page)
    return _single_column_pdf(markdown_text, one_page)


# ---------------------------------------------------------------------------
# Two-column renderer
# ---------------------------------------------------------------------------

def _parse_two_col_sections(text):
    """Split markdown into (header_lines, sidebar_lines, main_lines)."""
    header, sidebar, main = [], [], []
    section = "header"
    for line in text.split("\n"):
        s = line.strip()
        if s == "<<SIDEBAR>>":
            section = "sidebar"
        elif s == "<</SIDEBAR>>":
            section = "between"
        elif s == "<<MAIN>>":
            section = "main"
        elif s == "<</MAIN>>":
            section = "done"
        elif section == "header":
            header.append(line)
        elif section == "sidebar":
            sidebar.append(line)
        elif section == "main":
            main.append(line)
    return header, sidebar, main


def _two_column_pdf(markdown_text, one_page=True):
    pdf = ResumePDF()
    pdf.add_page()
    pdf.set_margins(_L_MARGIN, _T_MARGIN, _R_MARGIN)

    header_lines, sidebar_lines, main_lines = _parse_two_col_sections(markdown_text)

    # ── Full-width header ──────────────────────────────────────────────────
    for raw in header_lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# ") and not line.startswith("## "):
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_left_margin(_L_MARGIN)
            pdf.set_right_margin(_R_MARGIN)
            pdf.set_x(_L_MARGIN)
            pdf.cell(0, 8, _strip_md(line[2:]), align="C", new_x="LMARGIN", new_y="NEXT")
        elif "|" in line and not line.startswith("#") and not line.startswith("-"):
            pdf.set_font("Helvetica", "", 8)
            pdf.set_x(_L_MARGIN)
            pdf.cell(0, 4, _strip_md(line), align="C", new_x="LMARGIN", new_y="NEXT")

    # Thin rule under header
    y0 = pdf.get_y() + 2
    pdf.set_draw_color(80, 80, 80)
    pdf.set_line_width(0.35)
    pdf.line(_L_MARGIN, y0, _PAGE_W - _R_MARGIN, y0)
    col_start_y = y0 + 3

    # ── Left column (sidebar) ──────────────────────────────────────────────
    pdf.set_left_margin(_L_MARGIN)
    pdf.set_right_margin(_PAGE_W - _L_MARGIN - _LEFT_COL_W)
    pdf.set_xy(_L_MARGIN, col_start_y)
    _render_sidebar(pdf, sidebar_lines, one_page)
    left_end_y = pdf.get_y()

    # ── Right column (main) ────────────────────────────────────────────────
    pdf.set_left_margin(_RIGHT_COL_X)
    pdf.set_right_margin(_R_MARGIN)
    pdf.set_xy(_RIGHT_COL_X, col_start_y)
    _render_main(pdf, main_lines, one_page)
    right_end_y = pdf.get_y()

    # ── Vertical separator line ────────────────────────────────────────────
    sep_x  = _L_MARGIN + _LEFT_COL_W + _COL_GAP / 2
    col_end_y = min(max(left_end_y, right_end_y), pdf.h - 12)
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.2)
    pdf.line(sep_x, col_start_y, sep_x, col_end_y)

    # Reset margins
    pdf.set_left_margin(_L_MARGIN)
    pdf.set_right_margin(_R_MARGIN)

    _trim_to_one_page(pdf, one_page)
    return bytes(pdf.output())


def _render_sidebar(pdf, lines, one_page):
    """Render sidebar lines.  Left/right margins must already be set for this column."""
    lm = pdf.l_margin  # = _L_MARGIN

    for raw in lines:
        if one_page and pdf.page > 1:
            break
        line = raw.strip()
        if not line:
            pdf.ln(1.5)
            continue
        if line.startswith("## "):
            _section_header(pdf, line[3:], lm, _LEFT_COL_W, font_size=8)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.set_x(lm)
            pdf.multi_cell(_LEFT_COL_W, 4, _strip_md(line[4:]))
        elif _is_date_line(line):
            pdf.set_font("Helvetica", "I", 7)
            pdf.set_x(lm)
            pdf.multi_cell(_LEFT_COL_W, 3.5, _strip_md(line))
            pdf.ln(0.5)
        elif line.startswith("- ") or line.startswith("* "):
            _bullet_in_col(pdf, line[2:], lm, font_size=7.5, lh=4)
        elif line.startswith("---"):
            pass
        else:
            _inline_bold_in_col(pdf, line, lm, font_size=7.5, lh=4)


def _render_main(pdf, lines, one_page):
    """Render main column lines.  Left/right margins must already be set for this column."""
    col_x = pdf.l_margin  # = _RIGHT_COL_X
    col_w = _PAGE_W - _R_MARGIN - col_x

    for raw in lines:
        if one_page and pdf.page > 1:
            break
        line = raw.strip()
        if not line:
            pdf.ln(1.5)
            continue
        if line.startswith("## "):
            _section_header(pdf, line[3:], col_x, col_w, font_size=10)
        elif line.startswith("### "):
            pdf.ln(1)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_x(col_x)
            pdf.multi_cell(col_w, 5, _strip_md(line[4:]))
        elif _is_date_line(line):
            pdf.set_font("Helvetica", "I", 7.5)
            pdf.set_x(col_x)
            pdf.cell(col_w, 4, _strip_md(line), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.5)
        elif line.startswith("- ") or line.startswith("* "):
            _bullet_in_col(pdf, line[2:], col_x, font_size=8, lh=4.5)
        elif line.startswith("---"):
            pass
        else:
            _inline_bold_in_col(pdf, line, col_x, font_size=8, lh=4.5)


def _section_header(pdf, text, col_x, col_w, font_size=10):
    """Render a section label with a rule underneath."""
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", font_size)
    pdf.set_x(col_x)
    pdf.cell(col_w, 5, _strip_md(text).upper(), new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_draw_color(80, 80, 80)
    pdf.set_line_width(0.25)
    pdf.line(col_x, y, col_x + col_w, y)
    pdf.ln(1.5)


def _bullet_in_col(pdf, text, col_x, font_size=8, lh=4.5):
    """Render a hanging-indent bullet with inline bold within a column."""
    dash_x  = col_x + 2
    text_x  = dash_x + 4

    pdf.set_x(dash_x)
    pdf.set_font("Helvetica", "", font_size)
    pdf.cell(4, lh, "-", new_x="RIGHT", new_y="TOP")

    pdf.set_left_margin(text_x)
    pdf.set_x(text_x)
    _write_inline_parts(pdf, text, font_size, lh)
    pdf.ln(lh)

    pdf.set_left_margin(col_x)
    pdf.set_x(col_x)


def _inline_bold_in_col(pdf, text, col_x, font_size=8, lh=4.5):
    """Render a paragraph line with inline bold within a column."""
    pdf.set_x(col_x)
    _write_inline_parts(pdf, text, font_size, lh)
    pdf.ln(lh)


def _write_inline_parts(pdf, text, font_size, lh):
    """Write text with **bold** spans using pdf.write() — wraps at current margins."""
    text = _prep_inline(text)
    for part in re.split(r"(\*\*(?:(?!\*\*).)+?\*\*)", text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            pdf.set_font("Helvetica", "B", font_size)
            content = _sanitize_unicode(part[2:-2])
        else:
            pdf.set_font("Helvetica", "", font_size)
            content = _sanitize_unicode(part)
        if content:
            pdf.write(lh, content)


# ---------------------------------------------------------------------------
# Single-column renderer — tight one-page layout
# ---------------------------------------------------------------------------

def _single_column_pdf(markdown_text, one_page=True):
    lm, rm, tm = 10, 10, 9   # tighter margins (mm)
    body_fs = 7.5             # body font size (pt)
    body_lh = 4.2             # body line height (mm)

    pdf = ResumePDF()
    pdf.add_page()
    pdf.set_margins(lm, tm, rm)
    pdf.set_auto_page_break(auto=True, margin=9)

    lines = markdown_text.split("\n")
    i = 0
    in_skills_section = False

    while i < len(lines):
        if one_page and pdf.page > 1:
            break

        line = lines[i].strip()

        if not line:
            pdf.ln(1.0)
            i += 1
            continue

        # H1: candidate name
        if line.startswith("# ") and not line.startswith("## "):
            pdf.set_font("Helvetica", "B", 15)
            pdf.cell(0, 7, _strip_md(line[2:]), align="C", new_x="LMARGIN", new_y="NEXT")
            in_skills_section = False
            i += 1
            continue

        # Contact line (pipe-separated, contains @)
        if "|" in line and "@" in line and not line.startswith("#") and not line.startswith("-"):
            pdf.set_font("Helvetica", "", 7.5)
            pdf.cell(0, 3.5, _strip_md(line), align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.2)
            i += 1
            continue

        # H2: section headers
        if line.startswith("## "):
            section = _strip_md(line[3:])
            in_skills_section = section.upper() == "SKILLS"
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.cell(0, 5, section.upper(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(60, 60, 60)
            pdf.set_line_width(0.3)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(1.5)
            i += 1
            continue

        # H3: job title / project — dates now inline on same line
        if line.startswith("### "):
            in_skills_section = False
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_x(lm)
            _write_inline(pdf, line[4:], font_size=8.5, line_height=4.5)
            pdf.ln(4.5)
            i += 1
            continue

        # Bullet points
        if line.startswith("- ") or line.startswith("* "):
            _render_bullet(pdf, line[2:], font_size=body_fs, line_height=body_lh)
            i += 1
            continue

        # Horizontal rule — skip
        if line.startswith("---"):
            i += 1
            continue

        # Skills lines: render whole line (preserves | separator visually)
        if in_skills_section:
            _render_inline_bold(pdf, line, font_size=body_fs, line_height=body_lh)
            i += 1
            continue

        # Everything else: education, certifications, plain text
        if line:
            _render_inline_bold(pdf, line, font_size=body_fs, line_height=body_lh)

        i += 1

    _trim_to_one_page(pdf, one_page)
    return bytes(pdf.output())


def _trim_to_one_page(pdf, one_page):
    if one_page and pdf.page > 1:
        while pdf.page > 1:
            del pdf.pages[pdf.page]
            pdf.page -= 1


# ---------------------------------------------------------------------------
# Legacy helpers used by single-column path
# ---------------------------------------------------------------------------

def _render_bullet(pdf, text, font_size=8, line_height=4.5):
    original_lmargin = pdf.l_margin
    dash_indent = original_lmargin + 2
    text_indent  = dash_indent + 4

    pdf.set_x(dash_indent)
    pdf.set_font("Helvetica", "", font_size)
    pdf.cell(4, line_height, "-", new_x="RIGHT", new_y="TOP")

    pdf.set_left_margin(text_indent)
    pdf.set_x(text_indent)
    _write_inline(pdf, text, font_size, line_height)
    pdf.ln(line_height)

    pdf.set_left_margin(original_lmargin)
    pdf.set_x(original_lmargin)


def _render_inline_bold(pdf, text, font_size=8, line_height=4.5):
    _write_inline(pdf, text, font_size, line_height)
    pdf.ln(line_height)


def _write_inline(pdf, text, font_size=8, line_height=4.5):
    text = _prep_inline(text)
    for part in re.split(r"(\*\*(?:(?!\*\*).)+?\*\*)", text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            pdf.set_font("Helvetica", "B", font_size)
            content = _sanitize_unicode(part[2:-2])
        else:
            pdf.set_font("Helvetica", "", font_size)
            content = _sanitize_unicode(part)
        if content:
            pdf.write(line_height, content)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _prep_inline(text):
    """Strip non-bold markdown but PRESERVE **bold** markers."""
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_",   r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"`(.+?)`",   r"\1", text)
    return text


def _strip_md(text):
    """Remove ALL markdown formatting — for headers and cell text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"__(.+?)__",     r"\1", text)
    text = re.sub(r"_(.+?)_",       r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"`(.+?)`",       r"\1", text)
    return _sanitize_unicode(text).strip()


def _sanitize_unicode(text):
    """Replace Unicode chars that latin-1 can't encode."""
    replacements = {
        "\u2013": "-",   "\u2014": "-",   "\u2018": "'",  "\u2019": "'",
        "\u201c": '"',   "\u201d": '"',   "\u2026": "...","\u2022": "-",
        "\u00a0": " ",   "\u200b": "",    "\u2713": "v",  "\u2714": "v",
        "\u2192": "->",
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _is_date_line(line):
    """Heuristic: short line that looks like a date range."""
    clean = _strip_md(line)
    if len(clean) > 80:
        return False
    patterns = [
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
        r"\b\d{4}\b",
        r"\bPresent\b",
    ]
    return sum(1 for p in patterns if re.search(p, clean, re.IGNORECASE)) >= 2
