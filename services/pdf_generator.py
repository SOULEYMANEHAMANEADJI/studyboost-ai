"""PDF generation — robuste avec logo optionnel, pagination, marges propres."""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF


class StudyBoostPDF(FPDF):
    def __init__(self, title: str = "StudyBoost AI", logo_path: str | None = None):
        super().__init__()
        self.doc_title = title
        self.logo_path = logo_path if logo_path and Path(logo_path).exists() else None
        self.set_auto_page_break(auto=True, margin=25)
        self.set_margins(15, 15, 15)
        self.add_page()
        self.set_title(title)

    def header(self):
        if self.logo_path:
            try:
                self.image(self.logo_path, x=15, y=10, w=12)
            except Exception:
                pass
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(79, 70, 229)
        self.cell(0, 10, self.doc_title, ln=True, align="C")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, "Généré par StudyBoost AI", ln=True, align="C")
        self.ln(4)
        self.set_draw_color(226, 232, 240)
        self.line(15, self.get_y(), self.w - 15, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 116, 139)
        self.cell(0, 10, "Généré par StudyBoost AI", align="L")
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
    """Simple Markdown-to-plain-text preprocessing — ne déforme pas le contenu."""
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
    if logo_path and not os.path.exists(logo_path):
        logo_path = None
    title = title or generate_default_title()
    pdf = StudyBoostPDF(title=title, logo_path=logo_path)

    for raw_line in _plain_lines(text):
        line = raw_line.rstrip()
        if not line:
            pdf.ln(2)
            continue

        stripped = line.lstrip()
        if stripped.startswith("-") or stripped.startswith("*"):
            content = stripped[1:].strip()
            pdf.bullet_point(content)
        elif re.match(r"^\d+\.\s", stripped):
            content = re.sub(r"^\d+\.\s", "", stripped)
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(6)
            pdf.cell(5, 6, str(len(stripped.split(".")[0]) + 1), align="C") if False else None
            pdf.multi_cell(0, 6, content)
        else:
            pdf.chapter_body(line)

    return bytes(pdf.output(dest="S"))


def generate_default_title() -> str:
    return f"StudyBoost_{datetime.now().strftime('%Y%m%d_%H%M')}"
