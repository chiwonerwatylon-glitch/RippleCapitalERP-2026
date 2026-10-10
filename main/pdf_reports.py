"""PDF report generation. Every report starts with the Ripple Capital logo and name."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = BASE_DIR / "Logo.png"
COMPANY_NAME = "Ripple Capital Insurance"

BRAND = colors.HexColor("#1B702D")
BRAND_LIGHT = colors.HexColor("#E8F5EA")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#E5E7EB")
ZEBRA = colors.HexColor("#F9FAFB")

_STYLES = {
    "company": ParagraphStyle("company", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=BRAND),
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=INK),
    "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8.5, leading=11, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10, textColor=INK),
    "cell_r": ParagraphStyle("cell_r", fontName="Helvetica", fontSize=8, leading=10, textColor=INK, alignment=TA_RIGHT),
    "head": ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white),
    "head_r": ParagraphStyle("head_r", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white, alignment=TA_RIGHT),
    "sum_label": ParagraphStyle("sum_label", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=MUTED),
    "sum_value": ParagraphStyle("sum_value", fontName="Helvetica-Bold", fontSize=11, leading=13, textColor=INK),
}


def _cell_text(value):
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _logo(max_width, max_height):
    if not LOGO_PATH.exists():
        return ""
    width, height = ImageReader(str(LOGO_PATH)).getSize()
    scale = min(max_width / width, max_height / height)
    return Image(str(LOGO_PATH), width=width * scale, height=height * scale)


def build_report_pdf(title, headers, rows, subtitle="", numeric_cols=(),
                     col_weights=None, summary=None, empty_message="No records found."):
    """Return a BytesIO containing an A4 landscape PDF.

    The first page starts with the logo and company name; later pages carry the name in the header.
    """
    buffer = BytesIO()
    page_size = landscape(A4)
    margin = 14 * mm
    usable = page_size[0] - 2 * margin
    generated = datetime.now().strftime("%d %b %Y, %H:%M")
    right = set(numeric_cols)

    story = []

    # Brand block at the top of the document
    brand_text = [
        Paragraph(COMPANY_NAME, _STYLES["company"]),
        Paragraph(escape(title), _STYLES["title"]),
        Paragraph(
            escape(f"Generated {generated}" + (f"  ·  {subtitle}" if subtitle else "")),
            _STYLES["meta"],
        ),
    ]
    brand = Table([[_logo(30 * mm, 16 * mm), brand_text]], colWidths=[34 * mm, usable - 34 * mm])
    brand.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 1.5, BRAND),
    ]))
    story.append(brand)
    story.append(Spacer(1, 10))

    # Summary cards
    if summary:
        cell_w = usable / len(summary)
        summary_table = Table(
            [
                [Paragraph(escape(label.upper()), _STYLES["sum_label"]) for label, _ in summary],
                [Paragraph(escape(value), _STYLES["sum_value"]) for _, value in summary],
            ],
            colWidths=[cell_w] * len(summary),
        )
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEAFTER", (0, 0), (-2, -1), 0.5, colors.white),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 12))

    # Data table
    weights = col_weights or [1] * len(headers)
    total_weight = float(sum(weights))
    widths = [usable * w / total_weight for w in weights]

    data = [[
        Paragraph(escape(h), _STYLES["head_r" if i in right else "head"])
        for i, h in enumerate(headers)
    ]]
    for row in rows:
        data.append([
            Paragraph(escape(_cell_text(v)), _STYLES["cell_r" if i in right else "cell"])
            for i, v in enumerate(row)
        ])
    if not rows:
        data.append([Paragraph(escape(empty_message), _STYLES["cell"])] + [""] * (len(headers) - 1))

    table = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
    ]
    for r in range(2, len(data), 2):
        style.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
    if not rows:
        style.append(("SPAN", (0, 1), (-1, 1)))
    table.setStyle(TableStyle(style))
    story.append(table)

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 8 * mm, f"{COMPANY_NAME}  ·  {title}  ·  Confidential")
        canvas.drawRightString(page_size[0] - margin, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    def _later_pages(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(BRAND)
        canvas.drawString(margin, page_size[1] - 9 * mm, COMPANY_NAME)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(page_size[0] - margin, page_size[1] - 9 * mm, title)
        canvas.restoreState()
        _footer(canvas, doc)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"{COMPANY_NAME} - {title}",
        author=COMPANY_NAME,
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_later_pages)
    buffer.seek(0)
    return buffer

