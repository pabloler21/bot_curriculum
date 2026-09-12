# backend/adapter/renderer.py
"""
CV PDF Renderer — ATS-friendly single-column layout using ReportLab.

Design decisions:
- Helvetica throughout (no special fonts — ATS-safe)
- Single column, no tables, no graphics, no images
- Clear section headers as plain bold text
- Bullet points as "• " prefix (text character, parseable by ATS)
- Standard margins (0.75 inch)
- Returns bytes — caller handles response / storage
"""
import logging
from io import BytesIO
from typing import Optional

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from backend.schemas import CVSchema

logger = logging.getLogger(__name__)

# ── Style constants ────────────────────────────────────────────────────────────
_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
_COLOR_BLACK = "#1a1a1a"
_COLOR_GREY = "#555555"
_COLOR_RULE = "#cccccc"

_MARGIN = 0.75 * inch

_S_NAME = ParagraphStyle(
    "name",
    fontName=_FONT_BOLD,
    fontSize=20,
    leading=24,
    textColor=_COLOR_BLACK,
    alignment=TA_CENTER,
    spaceAfter=4,
)
_S_CONTACT = ParagraphStyle(
    "contact",
    fontName=_FONT,
    fontSize=9,
    leading=13,
    textColor=_COLOR_GREY,
    alignment=TA_CENTER,
    spaceAfter=10,
)
_S_SECTION = ParagraphStyle(
    "section",
    fontName=_FONT_BOLD,
    fontSize=11,
    leading=14,
    textColor=_COLOR_BLACK,
    spaceBefore=12,
    spaceAfter=2,
)
_S_ROLE = ParagraphStyle(
    "role",
    fontName=_FONT_BOLD,
    fontSize=10,
    leading=13,
    textColor=_COLOR_BLACK,
)
_S_COMPANY_DATE = ParagraphStyle(
    "company_date",
    fontName=_FONT,
    fontSize=9,
    leading=12,
    textColor=_COLOR_GREY,
    spaceAfter=3,
)
_S_BULLET = ParagraphStyle(
    "bullet",
    fontName=_FONT,
    fontSize=9,
    leading=13,
    textColor=_COLOR_BLACK,
    leftIndent=12,
    spaceAfter=1,
)
_S_BODY = ParagraphStyle(
    "body",
    fontName=_FONT,
    fontSize=9,
    leading=13,
    textColor=_COLOR_BLACK,
    spaceAfter=2,
)
_S_SKILLS = ParagraphStyle(
    "skills",
    fontName=_FONT,
    fontSize=9,
    leading=13,
    textColor=_COLOR_BLACK,
)


def _rule() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.5, color=_COLOR_RULE, spaceAfter=4)


def _safe(text: Optional[str]) -> str:
    """Escape HTML special chars for ReportLab Paragraph."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def render_pdf(schema: CVSchema) -> bytes:
    """
    Render an ATS-friendly PDF from CVSchema.

    Returns raw bytes. Raises on rendering failure.
    """
    logger.info("[renderer] Rendering PDF for %s", schema.candidate_name)
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(_safe(schema.candidate_name), _S_NAME))
    if schema.contact_info:
        story.append(Paragraph(_safe(schema.contact_info), _S_CONTACT))
    story.append(_rule())

    # ── Summary ───────────────────────────────────────────────────────────────
    if schema.summary:
        story.append(Paragraph("PROFESSIONAL SUMMARY", _S_SECTION))
        story.append(_rule())
        story.append(Paragraph(_safe(schema.summary), _S_BODY))

    # ── Experience ────────────────────────────────────────────────────────────
    if schema.experiences:
        story.append(Paragraph("EXPERIENCE", _S_SECTION))
        story.append(_rule())

        for exp in schema.experiences:
            story.append(Paragraph(_safe(exp.role), _S_ROLE))
            date_str = exp.start_date
            if exp.end_date:
                date_str += f" – {exp.end_date}"
            else:
                date_str += " – Present"
            story.append(
                Paragraph(f"{_safe(exp.company)} | {_safe(date_str)}", _S_COMPANY_DATE)
            )
            for bullet in exp.bullets:
                story.append(Paragraph(f"• {_safe(bullet)}", _S_BULLET))
            story.append(Spacer(1, 4))

    # ── Skills ────────────────────────────────────────────────────────────────
    if schema.skills:
        story.append(Paragraph("SKILLS", _S_SECTION))
        story.append(_rule())
        story.append(Paragraph(_safe(", ".join(schema.skills)), _S_SKILLS))

    # ── Education ─────────────────────────────────────────────────────────────
    if schema.education:
        story.append(Paragraph("EDUCATION", _S_SECTION))
        story.append(_rule())
        for edu in schema.education:
            degree_line = _safe(edu.degree)
            if edu.field:
                degree_line += f" — {_safe(edu.field)}"
            story.append(Paragraph(degree_line, _S_ROLE))
            details = _safe(edu.institution)
            if edu.year:
                details += f" | {_safe(edu.year)}"
            story.append(Paragraph(details, _S_COMPANY_DATE))

    # ── Languages & Certifications ────────────────────────────────────────────
    if schema.languages or schema.certifications:
        story.append(Paragraph("ADDITIONAL", _S_SECTION))
        story.append(_rule())
        if schema.languages:
            story.append(
                Paragraph(
                    f"<b>Languages:</b> {_safe(', '.join(schema.languages))}", _S_BODY
                )
            )
        if schema.certifications:
            for cert in schema.certifications:
                story.append(Paragraph(f"• {_safe(cert)}", _S_BULLET))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    logger.info("[renderer] PDF rendered, %d bytes", len(pdf_bytes))
    return pdf_bytes
