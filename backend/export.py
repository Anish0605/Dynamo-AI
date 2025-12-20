from fastapi import APIRouter, Body
import io

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from docx import Document
from pptx import Presentation

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/pdf")
def export_pdf(text: str = Body(..., embed=True)):
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer)
    story = [Paragraph(text.replace("\n", "<br/>"), styles["Normal"])]
    doc.build(story)

    return {"file": buffer.getvalue().hex()}


@router.post("/docx")
def export_docx(text: str = Body(..., embed=True)):
    document = Document()
    for line in text.split("\n"):
        document.add_paragraph(line)

    buffer = io.BytesIO()
    document.save(buffer)

    return {"file": buffer.getvalue().hex()}


@router.post("/pptx")
def export_pptx(text: str = Body(..., embed=True)):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])

    slide.shapes.title.text = "Dynamo AI Export"
    slide.placeholders[1].text = text[:4000]

    buffer = io.BytesIO()
    prs.save(buffer)

    return {"file": buffer.getvalue().hex()}
