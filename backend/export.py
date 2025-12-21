#export.py
import io
from docx import Document
from pptx import Presentation
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from fastapi.responses import StreamingResponse

def word(history):
    doc = Document(); doc.add_heading('Dynamo AI Research Report', 0)
    for m in history: doc.add_paragraph(f"{'User' if m['role']=='user' else 'AI'}: {m['content']}")
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

def ppt(history):
    prs = Presentation()
    for m in history[-5:]:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = "Research Insight"
        slide.placeholders[1].text = str(m['content'])[:700]
    buf = io.BytesIO(); prs.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")

def pdf(history):
    buf = io.BytesIO(); pdf_doc = SimpleDocTemplate(buf, pagesize=letter); styles = getSampleStyleSheet()
    story = [Paragraph("Dynamo AI Intelligence Report", styles['Title']), Spacer(1, 12)]
    for m in history:
        story.append(Paragraph(f"<b>{'User' if m['role']=='user' else 'AI'}:</b> {m['content']}", styles['Normal']))
        story.append(Spacer(1, 12))
    pdf_doc.build(story); buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf")