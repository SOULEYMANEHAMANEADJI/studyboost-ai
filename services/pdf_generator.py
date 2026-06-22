"""PDF generation helpers for StudyBoost AI."""
from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

from fpdf import FPDF


class StudyBoostPDF(FPDF):
    """Custom PDF document with header and footer."""

    def __init__(self, title: str = "StudyBoost AI", logo_path: str | None = None):
        super().__init__()
        self.doc_title = title
        self.logo_path = logo_path
        self.set_auto_page_break(auto=True, margin=20)
        self.add_page()
        self.set_title(title)

    def header(self):
        if self.logo_path and Path(self.logo_path).exists():
            try:
                self.image(self.logo_path, x=10, y=8, w=14)
            except Exception:
                pass
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(79, 70, 229)
        self.cell(0, 10, self.doc_title, ln=True, align="C")
        self.ln(6)
        self.set_draw_color(226, 232, 240)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 116, 139)
        self.cell(0, 10, "StudyBoost AI - Export confidentiel", align="L")
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="R")

    def chapter_title(self, title: str):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(31, 41, 59)
        self.multi_cell(0, 8, title)
        self.ln(2)

    def chapter_body(self, body: str):
        self.set_font("Helvetica", "", 11)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 6, body)
        self.ln()

    def bullet_point(self, text: str):
        self.set_font("Helvetica", "", 11)
        self.set_text_color(30, 41, 59)
        self.cell(6)
        self.cell(5, 6, chr(149), align="C")
        self.multi_cell(0, 6, text)


def _plain_lines(text: str) -> list[str]:
    """Simple Markdown-to-plain-text preprocessing."""
    # Headings
    text = re.sub(r"^###\s+(.*)$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.*)$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+(.*)$", r"\1", text, flags=re.MULTILINE)
    # Bold / italic markers
    text = re.sub(r"\*\*\*(.*?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    # Links [text](url) -> text (url)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", text)
    # Code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.splitlines()


def markdown_to_pdf(text: str, title: str | None = None, logo_path: str | None = None) -> bytes:
    """Convert Markdown text into a branded PDF bytes stream."""
    title = title or generate_default_title()
    pdf = StudyBoostPDF(title=title, logo_path=logo_path)

    in_bullets = False
    for raw_line in _plain_lines(text):
        line = raw_line.rstrip()
        if not line:
            in_bullets = False
            pdf.ln(2)
            continue

        stripped = line.lstrip()
        if stripped.startswith("-") or stripped.startswith("*"):
            in_bullets = True
            content = stripped[1:].strip()
            pdf.bullet_point(content)
        elif re.match(r"^\d+\.\s", stripped):
            in_bullets = True
            content = re.sub(r"^\d+\.\s", "", stripped)
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(6)
            pdf.cell(5, 6, "Â°", align="C")
            pdf.multi_cell(0, 6, content)
        elif len(line) < 60 and line.isupper():
            pdf.chapter_title(line)
        else:
            in_bullets = False
            pdf.chapter_body(line)

    return bytes(pdf.output(dest="S"))


def generate_default_title() -> str:
    return f"StudyBoost_{datetime.now().strftime('%Y%m%d_%H%M')}"
