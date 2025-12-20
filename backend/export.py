from fastapi import APIRouter, Body
import io, os
from datetime import datetime

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch

from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

from pptx import Presentation
from pptx.util import Inches, Pt

router = APIRouter(prefix="/export", tags=["Export"])

# =========================
# BRAND CONFIG
# =========================
BRAND_NAME = "Dynamo AI"
TAGLINE = "Power Your Curiosity"
DATE_STR = datetime.now().strftime("%d %b %Y")

# Place your logo here
LOGO_PATH = "assets/logo.png"   # <-- put your logo here (png)


# =========================
# HELPER
# =========================
def format_messages(messages):
    blocks = []
    for m in messages:
        role = m.get("role", "").upper()
        content = m.get("content", "")
        blocks.append(f"{role}:\n{content}")
    return "\n\n".join(blocks)


# =========================
# PDF EXPORT (PREMIUM)
# =========================
@router.post("/pdf")
def export_pdf(payload: dict = Body(...)):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "Title",
        fontSize=22,
        spaceAfter=14,
        alignment=1
    )

    meta_style = ParagraphStyle(
        "Meta",
        fontSize=10,
        textColor="grey",
        alignment=1,
        spaceAfter=20
    )

    body_style = ParagraphStyle(
        "Body",
        fontSize=12,
        spaceAfter=12
    )

    story = []

    # ---- Cover Page ----
    if os.path.exists(LOGO_PATH):
        story.append(Image(LOGO_PATH, width=2*inch, height=2*inch))
        story.append(Spacer(1, 20))

    story.append(Paragraph(BRAND_NAME, title_style))
    story.append(Paragraph(TAGLINE, meta_style))
    story.append(Paragraph(f"Generated on {DATE_STR}", meta_style))
    story.append(PageBreak())

    # ---- Content ----
    messages = payload.get("messages", [])
    text = format_messages(messages)

    for line in text.split("\n"):
        if line.strip():
            story.append(Paragraph(line.replace("<", "&lt;"), body_style))

    doc.build(story)
    return {"file": buffer.getvalue().hex()}


# =========================
# WORD EXPORT (PREMIUM)
# =========================
@router.post("/docx")
def export_docx(payload: dict = Body(...)):
    doc = Document()

    # ---- Logo ----
    if os.path.exists(LOGO_PATH):
        p = doc.add_paragraph()
        run = p.add_run()
        run.add_picture(LOGO_PATH, width=Inches(2))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ---- Branding ----
    h = doc.add_heading(BRAND_NAME, 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    t = doc.add_paragraph(TAGLINE)
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER

    d = doc.add_paragraph(f"Generated on {DATE_STR}")
    d.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_page_break()

    # ---- Content ----
    messages = payload.get("messages", [])
    for m in messages:
        role = m.get("role", "").upper()
        content = m.get("content", "")

        rp = doc.add_paragraph(role)
        rp.runs[0].bold = True

        cp = doc.add_paragraph(content)
        for run in cp.runs:
            run.font.size = Pt(11)

    buffer = io.BytesIO()
    doc.save(buffer)
    return {"file": buffer.getvalue().hex()}


# =========================
# PPT EXPORT (EXECUTIVE STYLE)
# =========================
@router.post("/pptx")
def export_pptx(payload: dict = Body(...)):
    prs = Presentation()

    # ---- Cover Slide ----
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    left = Inches(3)
    top = Inches(2)

    if os.path.exists(LOGO_PATH):
        slide.shapes.add_picture(LOGO_PATH, left, top, width=Inches(2))

    # ---- Slides per message ----
    messages = payload.get("messages", [])

    for i, m in enumerate(messages, start=1):
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = f"{m.get('role','').title()} {i}"
        slide.placeholders[1].text = m.get("content", "")[:3500]

    buffer = io.BytesIO()
    prs.save(buffer)
    return {"file": buffer.getvalue().hex()}
