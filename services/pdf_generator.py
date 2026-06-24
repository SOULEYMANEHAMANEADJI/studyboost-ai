"""
Générateur PDF professionnel avec reportlab.
Supporte UTF-8 (français, emojis) et Markdown.
"""
import os
import re
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    ListItem, ListFlowable
)

try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    pdfmetrics = None
    TTFont = None


FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")

_PRIMARY_FONT = "NotoSans"
_BOLD_FONT = "NotoSans-Bold"
_ITALIC_FONT = "NotoSans-Italic"
_EMOJI_FONT = "NotoEmoji"

_FONTS_REGISTERED = False

def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return True
    if pdfmetrics is None or TTFont is None:
        return False
    font_files = {
        _PRIMARY_FONT: "NotoSans-Regular.ttf",
        _BOLD_FONT: "NotoSans-Bold.ttf",
        _ITALIC_FONT: "NotoSans-Italic.ttf",
        _EMOJI_FONT: "NotoEmoji-Regular.ttf",
    }
    success = True
    for name, filename in font_files.items():
        path = os.path.join(FONTS_DIR, filename)
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                success = False
        else:
            success = False
    _FONTS_REGISTERED = success
    return success

_register_fonts()

EMOJI_RE = re.compile(
    "["
    "\U000000A9\U000000AE"                    # © ®
    "\U0000200D\U000020E3"                    # ZWJ, combining keycap
    "\U00002122\U00002139"                    # ™ ℹ
    "\U00002194-\U00002199"                   # Arrows
    "\U000021A9-\U000021AA"                   # ↩ ↪
    "\U0000231A-\U0000231B"                   # ⌚ ⌛
    "\U00002328\U000023CF"                    # ⌨ ⏏
    "\U000023E9-\U000023FA"                   # Media/time buttons
    "\U000024C2"                              # Ⓜ
    "\U000025AA-\U000025AB"                   # ▪ ▫
    "\U000025B6\U000025C0"                    # ▶ ◀
    "\U000025FB-\U000025FE"                   # ◻ ◼ ◽ ◾
    "\U00002600-\U000027BF"                   # ☀-➿ (misc symbols + dingbats)
    "\U00002934-\U00002935"                   # ⤴ ⤵
    "\U00002B05-\U00002B07"                   # ⬅ ⬆ ⬇
    "\U00002B1B-\U00002B1C"                   # ⬛ ⬜
    "\U00002B50\U00002B55"                    # ⭐ ⭕
    "\U00003030\U0000303D"                    # 〰 〽
    "\U00003297\U00003299"                    # 🈗 🈙
    "\U0000FE00-\U0000FE0F"                   # Variation selectors
    "\U0001F000-\U0001FAFF"                   # Full emoji range
    "]+"
)

def _wrap_emojis(text: str) -> str:
    if not _FONTS_REGISTERED:
        return text
    return EMOJI_RE.sub(lambda m: f'<font name="{_EMOJI_FONT}">{m.group(0)}</font>', text)


PRIMARY_COLOR = HexColor("#4F46E5")
TEXT_COLOR = HexColor("#1E293B")
GRAY_COLOR = HexColor("#64748B")
LIGHT_GRAY = HexColor("#94A3B8")





def generate_default_title() -> str:
    return f"StudyBoost_{datetime.now().strftime('%Y%m%d_%H%M')}"


class _PDFWithHeaderFooter:
    def __init__(self, logo_path: str | None = None, doc_title: str = "StudyBoost AI", neutral: bool = False):
        self.logo_path = logo_path if logo_path and os.path.exists(logo_path) else None
        self.doc_title = doc_title
        self.neutral = neutral

    def header_footer(self, canvas_obj, doc):
        canvas_obj.saveState()

        if self.logo_path:
            try:
                canvas_obj.drawImage(
                    self.logo_path,
                    1.5 * cm, A4[1] - 2.2 * cm,
                    width=1.2 * cm, height=1.2 * cm,
                    preserveAspectRatio=True, mask="auto",
                )
                text_x = 3.2 * cm
            except Exception:
                text_x = 1.5 * cm
        else:
            text_x = 1.5 * cm

        if not self.neutral:
            canvas_obj.setFillColor(PRIMARY_COLOR)
            canvas_obj.setFont(_BOLD_FONT if _FONTS_REGISTERED else "Helvetica-Bold", 13)
            canvas_obj.drawString(text_x, A4[1] - 1.5 * cm, "StudyBoost AI")

            canvas_obj.setFillColor(GRAY_COLOR)
            canvas_obj.setFont(_PRIMARY_FONT if _FONTS_REGISTERED else "Helvetica", 8)
            canvas_obj.drawString(text_x, A4[1] - 2 * cm, self.doc_title)

            canvas_obj.setStrokeColor(PRIMARY_COLOR)
            canvas_obj.setLineWidth(0.8)
            canvas_obj.line(1.5 * cm, A4[1] - 2.5 * cm, A4[0] - 1.5 * cm, A4[1] - 2.5 * cm)

            canvas_obj.setFillColor(LIGHT_GRAY)
            canvas_obj.setFont(_ITALIC_FONT if _FONTS_REGISTERED else "Helvetica-Oblique", 8)
            canvas_obj.drawString(1.5 * cm, 1 * cm, "Généré par StudyBoost AI")

        canvas_obj.setStrokeColor(HexColor("#E2E8F0"))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(1.5 * cm, 1.5 * cm, A4[0] - 1.5 * cm, 1.5 * cm)

        page_num = canvas_obj.getPageNumber()
        if not self.neutral:
            canvas_obj.drawRightString(
                A4[0] - 1.5 * cm, 1 * cm,
                f"Page {page_num}",
            )
        else:
            canvas_obj.drawCentredString(
                A4[0] / 2, 1 * cm,
                f"— {page_num} —",
            )

        canvas_obj.restoreState()


def _parse_md_to_flowables(text: str, styles: dict) -> list:
    flowables = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            flowables.append(Spacer(1, 0.2 * cm))
            i += 1
            continue

        line_html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        line_html = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", line_html)
        line_html = re.sub(
            r"`(.+?)`",
            r'<font name="Courier" color="#7C3AED">\1</font>',
            line_html,
        )

        if line.startswith("### "):
            flowables.append(Paragraph(_wrap_emojis(line_html[4:]), styles["h3"]))
            flowables.append(Spacer(1, 0.15 * cm))
        elif line.startswith("## "):
            flowables.append(Paragraph(_wrap_emojis(line_html[3:]), styles["h2"]))
            flowables.append(Spacer(1, 0.2 * cm))
        elif line.startswith("# "):
            flowables.append(Paragraph(_wrap_emojis(line_html[2:]), styles["h1"]))
            flowables.append(Spacer(1, 0.3 * cm))
        elif line.lstrip().startswith(("- ", "* ")):
            items = []
            while i < len(lines) and lines[i].lstrip().startswith(("- ", "* ")):
                t = lines[i].lstrip()[2:]
                t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
                t = re.sub(r"`(.+?)`", r'<font name="Courier" color="#7C3AED">\1</font>', t)
                items.append(ListItem(Paragraph(_wrap_emojis(t), styles["body"]), leftIndent=10))
                i += 1
            flowables.append(ListFlowable(items, bulletType="bullet", start="•", bulletColor=PRIMARY_COLOR))
            flowables.append(Spacer(1, 0.15 * cm))
            continue
        elif re.match(r"^\d+\.\s", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i]):
                t = re.sub(r"^\d+\.\s", "", lines[i])
                t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
                items.append(ListItem(Paragraph(_wrap_emojis(t), styles["body"]), leftIndent=10))
                i += 1
            flowables.append(ListFlowable(items, bulletType="1", bulletColor=PRIMARY_COLOR))
            flowables.append(Spacer(1, 0.15 * cm))
            continue
        elif line.startswith("> "):
            flowables.append(Paragraph(_wrap_emojis(line_html[2:]), styles["quote"]))
            flowables.append(Spacer(1, 0.15 * cm))
        elif line.strip() in ("---", "***", "___"):
            flowables.append(Spacer(1, 0.3 * cm))
        else:
            flowables.append(Paragraph(_wrap_emojis(line_html), styles["body"]))
            flowables.append(Spacer(1, 0.1 * cm))

        i += 1

    return flowables


def markdown_to_pdf(text: str, title: str | None = None, logo_path: str | None = None, neutral: bool = False) -> bytes:
    if not title:
        title = generate_default_title()

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=3 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        title=title,
        author="StudyBoost AI" if not neutral else "",
    )

    base = getSampleStyleSheet()
    styles = {
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=20, textColor=TEXT_COLOR, fontName=_BOLD_FONT if _FONTS_REGISTERED else "Helvetica-Bold", spaceAfter=10, leading=24),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=15, textColor=PRIMARY_COLOR, fontName=_BOLD_FONT if _FONTS_REGISTERED else "Helvetica-Bold", spaceAfter=8, leading=18),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=12, textColor=TEXT_COLOR, fontName=_BOLD_FONT if _FONTS_REGISTERED else "Helvetica-Bold", spaceAfter=6, leading=15),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=10, textColor=TEXT_COLOR, fontName=_PRIMARY_FONT if _FONTS_REGISTERED else "Helvetica", leading=14, alignment=TA_LEFT),
        "quote": ParagraphStyle("quote", parent=base["BodyText"], fontSize=10, textColor=GRAY_COLOR, fontName=_ITALIC_FONT if _FONTS_REGISTERED else "Helvetica-Oblique", leftIndent=20, leading=14),
    }

    flowables = _parse_md_to_flowables(text, styles)
    hf = _PDFWithHeaderFooter(logo_path=logo_path, doc_title=title, neutral=neutral)

    doc.build(flowables, onFirstPage=hf.header_footer, onLaterPages=hf.header_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
