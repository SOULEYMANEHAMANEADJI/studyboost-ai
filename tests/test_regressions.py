import io
import unittest
from unittest.mock import patch

from docx import Document
import pymupdf as fitz
from services.editor_state import apply_pending_editor_text, stage_editor_text, editor_value
from services.markup import safe_markdown
from services.pdf_generator import markdown_to_pdf
from services.pdf_reader import extract_pdf_info, PDFImportError, MAX_PDF_PAGES, _extract_document
from services.docx_generator import markdown_to_docx


class RegressionTests(unittest.TestCase):
    def test_ai_result_replaces_existing_widget_on_next_run(self):
        state = {"editor_text":"old", "editor_textarea":"old"}
        stage_editor_text(state, "AI result")
        self.assertEqual(editor_value(state), "old")
        apply_pending_editor_text(state)
        self.assertEqual(editor_value(state), "AI result")
        self.assertEqual(state["editor_text"], "AI result")
        state["editor_textarea"] = "manual edit"
        self.assertEqual(editor_value(state), "manual edit")

    def test_preview_removes_active_html_and_resources(self):
        html = safe_markdown('# Titre\n\n**Gras** <script>steal()</script><style>body{display:none}</style><img src="https://example.invalid/x" onerror="bad()">[lien](javascript:alert)')
        for bad in ["<script", "<style", "<img", "onerror", "javascript:", "steal()"]:
            self.assertNotIn(bad, html)
        self.assertIn("<strong>Gras</strong>", html)
        self.assertIn("<h1>Titre</h1>", html)

    def test_pdf_escapes_untrusted_markup_without_fetching(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("Network forbidden")):
            data = markdown_to_pdf('# Cours\n\n<img src="https://example.invalid/test">\n\n- **A** & B < C', neutral=True)
        with fitz.open(stream=data, filetype="pdf") as doc:
            text = "".join(page.get_text() for page in doc)
            self.assertIn("example.invalid", text)
            self.assertIn("B < C", text)

    def test_docx_lists_have_no_duplicates_and_keep_spaces(self):
        data = markdown_to_docx('- Un **mot** utile\n1. Deux mots')
        doc = Document(io.BytesIO(data))
        texts = [p.text for p in doc.paragraphs]
        self.assertIn("Un mot utile", texts)
        self.assertIn("Deux mots", texts)
        self.assertNotIn("Deux motsDeux mots", texts)

    def test_invalid_and_overlong_pdf_are_rejected(self):
        with self.assertRaises(PDFImportError): extract_pdf_info(b"%PDF-invalid")
        with fitz.open() as doc:
            for _ in range(MAX_PDF_PAGES + 1): doc.new_page()
            data = doc.tobytes()
        with self.assertRaisesRegex(PDFImportError, "pages"):
            extract_pdf_info(data)
        class Page:
            def get_text(self, kind):
                return {"blocks":[{"type":0, "lines":[{"spans":[{"text":"x"*16000,"size":12,"flags":0}]}]}]}
        with self.assertRaises(PDFImportError): _extract_document([Page()])

    def test_valid_pdf_roundtrip(self):
        data = markdown_to_pdf("# Biologie\n\nLa cellule est une unite du vivant.", title="biologie", neutral=True)
        info = extract_pdf_info(data, "biologie.pdf")
        self.assertEqual(info.title, "biologie.pdf"[:-4])
        self.assertIn("cellule", info.text)


if __name__ == "__main__": unittest.main()
