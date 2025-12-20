from fastapi import APIRouter, Body
from fastapi.responses import FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from docx import Document
from pptx import Presentation
import uuid, os

router = APIRouter(prefix="/export")

BASE = os.path.dirname(__file__)
LOGO = os.path.join(BASE, "assets/logo.png")

@router.post("/pdf")
def pdf(data: dict = Body(...)):
    text = data.get("content", "")
    name = f"/tmp/{uuid.uuid4()}.pdf"
    c = canvas.Canvas(name, pagesize=A4)
    if os.path.exists(LOGO):
        c.drawImage(LOGO, 240, 760, width=120, height=120)
    c.drawString(50, 650, "Dynamo AI")
    y = 620
    for line in text.split("\n"):
        c.drawString(50, y, line[:100])
        y -= 14
    c.save()
    return FileResponse(name, filename="dynamo.pdf")

@router.post("/word")
def word(data: dict = Body(...)):
    doc = Document()
    doc.add_heading("Dynamo AI", 0)
    doc.add_paragraph(data.get("content",""))
    name = f"/tmp/{uuid.uuid4()}.docx"
    doc.save(name)
    return FileResponse(name, filename="dynamo.docx")

@router.post("/ppt")
def ppt(data: dict = Body(...)):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Dynamo AI"
    slide.placeholders[1].text = data.get("content","")[:3000]
    name = f"/tmp/{uuid.uuid4()}.pptx"
    prs.save(name)
    return FileResponse(name, filename="dynamo.pptx")
