"""Synthetic PDF builders for V2-20 tests (no real documents, no licensing questions).

Vietnamese text needs a TrueType font with Vietnamese glyphs. ``find_font`` looks at
``SOPILOT_TEST_FONT``, then common system locations; tests that need it skip when none exists.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

_FONT_CANDIDATES = [
    os.environ.get("SOPILOT_TEST_FONT", ""),
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]


def find_font() -> str | None:
    for candidate in _FONT_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _styles(font: str | None):
    base = getSampleStyleSheet()
    if font is None:
        return base["Heading1"], base["Heading2"], base["Normal"]
    if "SopilotTest" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("SopilotTest", font))
    h1 = ParagraphStyle("h1", parent=base["Heading1"], fontName="SopilotTest")
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontName="SopilotTest")
    body = ParagraphStyle("body", parent=base["Normal"], fontName="SopilotTest")
    return h1, h2, body


def _grid(rows, spans=()):
    table = Table(rows, repeatRows=1)
    style = [("GRID", (0, 0), (-1, -1), 0.5, colors.black)]
    style += [("SPAN", a, b) for a, b in spans]
    table.setStyle(TableStyle(style))
    return table


def build(story) -> bytes:
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4).build(story)
    return buf.getvalue()


def english_procedure() -> bytes:
    h1, _, body = _styles(None)
    rows = [["Step", "Action", "Owner", "Output"],
            ["1", "Prepare request", "Staff", "Form A"],
            ["2", "Review the request carefully", "Manager", "Approval"]]
    return build([
        Paragraph("1. Purpose", h1),
        Paragraph("This procedure describes how requests are handled and who is responsible "
                  "for each step of the process.", body),
        Paragraph("2. Procedure", h1),
        _grid(rows),
        PageBreak(),
        Paragraph("3. Records", h1),
        Paragraph("Records are kept for five years after the request is closed.", body),
    ])


def vietnamese_procedure(font: str) -> bytes:
    h1, h2, body = _styles(font)
    return build([
        Paragraph("1. Mục đích", h1),
        Paragraph("Quy trình này quy định việc tiếp nhận và xử lý đề nghị mua hàng trong công ty, "
                  "bảo đảm đúng thẩm quyền và lưu trữ đầy đủ hồ sơ.", body),
        Paragraph("2. Phạm vi áp dụng", h1),
        Paragraph("2.1. Đối tượng", h2),
        Paragraph("Áp dụng cho tất cả các phòng ban có phát sinh nhu cầu mua sắm.", body),
        Paragraph("a) Đơn hàng dưới 50 triệu đồng do Trưởng phòng phê duyệt.", body),
        Paragraph("b) Đơn hàng từ 50 triệu đồng do Giám đốc phê duyệt.", body),
    ])


def continued_table() -> bytes:
    h1, _, body = _styles(None)
    header = ["No.", "Task", "Owner", "Record"]
    page1 = [header] + [[str(i), f"Task number {i}", "Staff", "Form"] for i in range(1, 4)]
    page2 = [header] + [[str(i), f"Task number {i}", "Manager", "Log"] for i in range(4, 7)]
    return build([
        Paragraph("1. Responsibilities", h1),
        _grid(page1),
        PageBreak(),
        _grid(page2),
    ])


def text_page_then_image_page() -> bytes:
    """Page 1 has text; page 2 has only a picture of text (must yield 0 characters, no OCR)."""
    from PIL import Image, ImageDraw
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    img = Image.new("RGB", (800, 200), "white")
    ImageDraw.Draw(img).text((20, 80), "SCANNED PAGE TEXT THAT MUST NOT BE READ", fill="black")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 12)
    for i in range(30):
        c.drawString(72, 780 - i * 14, f"Line {i + 1}: this page carries a real text layer.")
    c.showPage()
    c.drawImage(ImageReader(img), 72, 500, width=400, height=100)
    c.showPage()
    c.save()
    return buf.getvalue()


def image_only() -> bytes:
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(Image.new("RGB", (400, 200), "white")), 72, 500, 300, 150)
    c.showPage()
    c.save()
    return buf.getvalue()


def encrypted() -> bytes:
    from reportlab.lib.pdfencrypt import StandardEncryption
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, encrypt=StandardEncryption("secret", canPrint=0))
    c.drawString(72, 700, "Confidential text " * 20)
    c.showPage()
    c.save()
    return buf.getvalue()
