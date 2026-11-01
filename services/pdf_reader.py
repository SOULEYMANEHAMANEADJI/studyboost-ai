"""
Extraction de texte PDF vers Markdown via pymupdf (fitz).
Supporte texte, titres, listes à puces, tableaux basiques.
"""
from __future__ import annotations

import re
from datetime import datetime

import pymupdf as fitz

_BULLET_RE = re.compile(r"^\s*[•\-▪▸►○●◆◇☑☒✓✔✗✘\*]\s*")

MAX_PDF_PAGES = 50
MAX_EXTRACTED_CHARS = 15000


class PDFImportError(ValueError):
    pass


MAX_UPLOAD_SIZE_MB = 5
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


class PDFInfo:
    def __init__(self, text: str, title: str, author: str, pages: int):
        self.text = text
        self.title = title
        self.author = author
        self.pages = pages


def extract_pdf_info(pdf_bytes: bytes, filename: str = "") -> PDFInfo:
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            if doc.needs_pass:
                raise PDFImportError("Ce PDF est protégé par un mot de passe.")
            if doc.page_count > MAX_PDF_PAGES:
                raise PDFImportError(f"Le PDF dépasse {MAX_PDF_PAGES} pages. Importe un extrait plus court.")
            meta = doc.metadata or {}
            title = (meta.get("title") or "").strip()
            if not title:
                title = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE).strip() if filename else f"Document_{datetime.now().strftime('%Y%m%d_%H%M')}"
            text = extract_text_from_pdf(pdf_bytes, doc)
            if not text.strip():
                raise PDFImportError("Aucun texte détecté. Les PDF scannés nécessitent une reconnaissance OCR.")
            return PDFInfo(text, title[:100], (meta.get("author") or "").strip(), doc.page_count)
    except PDFImportError:
        raise
    except Exception:
        raise PDFImportError("Ce fichier PDF est invalide ou illisible. Essaie un autre fichier.") from None


def extract_text_from_pdf(pdf_bytes: bytes, doc=None) -> str:
    own_doc = doc is None
    if own_doc:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.page_count > MAX_PDF_PAGES:
            raise PDFImportError(f"Le PDF dépasse {MAX_PDF_PAGES} pages.")
        return _extract_document(doc)
    finally:
        if own_doc:
            doc.close()


def _extract_document(doc) -> str:
    lines = []
    total_chars = 0
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

                total_chars += len(line_text) + 1
                if total_chars > MAX_EXTRACTED_CHARS:
                    raise PDFImportError(f"Le texte dépasse {MAX_EXTRACTED_CHARS:,} caractères. Importe un extrait plus court.")
                lines.append(line_text)
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


def pdf_bytes_to_markdown(uploaded_file) -> PDFInfo:
    pdf_bytes = uploaded_file.getvalue()
    if not pdf_bytes or pdf_bytes[:4] != b"%PDF":
        raise PDFImportError("Sélectionne un fichier PDF valide.")
    if len(pdf_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise PDFImportError(f"Le fichier dépasse {MAX_UPLOAD_SIZE_MB} Mo.")
    return extract_pdf_info(pdf_bytes, uploaded_file.name)
