"""
Extraction de texte PDF vers Markdown via pymupdf (fitz).
Supporte texte, titres, listes à puces, tableaux basiques.
"""
from __future__ import annotations

import re
from datetime import datetime

import fitz

_BULLET_RE = re.compile(r"^\s*[•\-▪▸►○●◆◇☑☒✓✔✗✘\*]\s*")

MAX_UPLOAD_SIZE_MB = 5
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


class PDFInfo:
    def __init__(self, text: str, title: str, author: str, pages: int):
        self.text = text
        self.title = title
        self.author = author
        self.pages = pages


def extract_pdf_info(pdf_bytes: bytes, filename: str = "") -> PDFInfo:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    meta = doc.metadata or {}

    title = (meta.get("title") or "").strip()
    author = (meta.get("author") or "").strip()
    pages = doc.page_count

    if not title:
        if filename:
            title = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE).strip()
        else:
            title = f"Document_{datetime.now().strftime('%Y%m%d_%H%M')}"

    title = title[:100]

    text = extract_text_from_pdf(pdf_bytes, doc)
    doc.close()
    return PDFInfo(text=text, title=title, author=author, pages=pages)


def extract_text_from_pdf(pdf_bytes: bytes, doc=None) -> str:
    own_doc = doc is None
    if own_doc:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    lines = []

    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue

            for line in block["lines"]:
                parts = []
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue

                    flags = span.get("flags", 0)
                    is_bold = bool(flags & 2**3)
                    is_italic = bool(flags & 2**1)
                    font_size = span.get("size", 12)

                    if is_bold and is_italic:
                        text = f"***{text}***"
                    elif is_bold:
                        text = f"**{text}**"
                    elif is_italic:
                        text = f"*{text}*"

                    if font_size >= 18:
                        text = f"# {text}"
                    elif font_size >= 15:
                        text = f"## {text}"
                    elif font_size >= 13:
                        text = f"### {text}"

                    parts.append(text)

                line_text = " ".join(parts).strip()
                if _BULLET_RE.match(line_text):
                    cleaned_line = _BULLET_RE.sub("", line_text)
                    line_text = f"- {cleaned_line}"

                lines.append(line_text)

    if own_doc:
        doc.close()
    return _cleanup_text("\n".join(lines))


def _cleanup_text(text: str) -> str:
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r" +\n", "\n", text)
    lines = [line.rstrip() for line in text.split("\n")]
    cleaned = []
    for line in lines:
        if not line.strip() and cleaned and not cleaned[-1].strip():
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def pdf_bytes_to_markdown(uploaded_file) -> PDFInfo | None:
    pdf_bytes = uploaded_file.read()
    if not pdf_bytes:
        return None

    if len(pdf_bytes) > MAX_UPLOAD_SIZE_BYTES:
        return None

    if pdf_bytes[:4] != b"%PDF":
        return None

    info = extract_pdf_info(pdf_bytes, uploaded_file.name)
    if not info.text.strip():
        return None

    return info
