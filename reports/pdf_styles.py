"""Shared PDF styling utilities for ReportLab reports."""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle

from config import PDF_HEADER_BG, PDF_TEXT_PRIMARY, PDF_BORDER

# Shared ReportLab color objects
DARK = colors.HexColor(PDF_TEXT_PRIMARY)
HEADER_BG = colors.HexColor(PDF_HEADER_BG)
BORDER = colors.HexColor(PDF_BORDER)
MUTED = colors.HexColor("#6B7280")
LIGHT_BG = colors.HexColor("#F9FAFB")


def build_base_styles():
    """Return base ParagraphStyles shared across all reports.

    Returns a dict with keys: title, subtitle, headline, section, body,
    caption, bullet, footer_note.
    """
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PTitle", parent=base["Heading1"], fontSize=22,
            textColor=DARK, spaceAfter=4, alignment=TA_LEFT,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "PSub", parent=base["Normal"], fontSize=11,
            textColor=MUTED, spaceAfter=6, alignment=TA_LEFT,
        ),
        "headline": ParagraphStyle(
            "PHeadline", parent=base["Normal"], fontSize=13,
            textColor=DARK, spaceAfter=14, spaceBefore=10,
            leading=18, fontName="Helvetica",
        ),
        "section": ParagraphStyle(
            "PSection", parent=base["Heading2"], fontSize=14,
            textColor=DARK, spaceAfter=10, spaceBefore=16,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "PBody", parent=base["Normal"], fontSize=10,
            textColor=DARK, spaceAfter=6,
        ),
        "caption": ParagraphStyle(
            "PCaption", parent=base["Normal"], fontSize=9,
            textColor=MUTED, spaceAfter=10, spaceBefore=4,
        ),
        "bullet": ParagraphStyle(
            "PBullet", parent=base["Normal"], fontSize=10,
            textColor=DARK, spaceAfter=5, leftIndent=16,
            bulletIndent=4, bulletFontName="Helvetica", bulletFontSize=10,
        ),
        "footer_note": ParagraphStyle(
            "PFooter", parent=base["Normal"], fontSize=9,
            textColor=MUTED, spaceBefore=20, alignment=TA_LEFT,
        ),
    }


def styled_table(data, col_widths, compact=False):
    """Create a consistently styled table with header row.

    Args:
        data: List of lists (first row = header).
        col_widths: List of column widths.
        compact: If True, use smaller font and tighter padding (for average_day report).
    """
    font_size = 9 if compact else 10
    header_font_size = 9 if compact else 11
    padding = 6 if compact else 10
    header_padding = 8 if compact else 12

    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), header_font_size),
        ("BOTTOMPADDING", (0, 0), (-1, 0), header_padding),
        ("TOPPADDING", (0, 0), (-1, 0), header_padding),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, BORDER),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), font_size),
        ("TOPPADDING", (0, 1), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 1), (-1, -1), padding),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
    ]))
    return t


def kpi_row(labels_values):
    """Render a single-row table of KPI cards (label/value pairs)."""
    header = [lv[0] for lv in labels_values]
    values = [lv[1] for lv in labels_values]
    n = len(labels_values)
    col_w = 6.5 * inch / n

    t = Table([header, values], colWidths=[col_w] * n)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 16),
        ("ALIGN", (0, 1), (-1, 1), "CENTER"),
        ("TOPPADDING", (0, 1), (-1, 1), 12),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
        ("TEXTCOLOR", (0, 1), (-1, 1), DARK),
        ("GRID", (0, 0), (-1, -1), 1, BORDER),
    ]))
    return t
