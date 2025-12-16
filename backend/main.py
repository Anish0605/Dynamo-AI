# main.py - Final (With Export Support)
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import google.generativeai as genai
from tavily import TavilyClient
from dotenv import load_dotenv
from pypdf import PdfReader
from PIL import Image
import io
import shutil
import time

# --- REPORT GENERATION IMPORTS ---
from docx import Document
from pptx import Presentation
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

gemini_model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")

tavily = None
if TAVILY_API_KEY:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)

class ChatRequest(BaseModel):
    message: str
    history: list = []
    use_search: bool = True
    deep_dive: bool = False
    model: str = "gemini-2.0-flash"
    pdf_context: str = None

# --- CHAT ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not gemini_model: raise HTTPException(500, "Gemini Key Missing")
    try:
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean}?nologo=true"}

        context_str = ""
        if req.use_search and not req.pdf_context and tavily:
            try:
                res = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic", max_results=3)
                context_str += f"\n\n[WEB]:\n{res.get('results', [])}\n"
            except: pass

        if req.pdf_context:
            context_str += f"\n\n[DOC]:\n{req.pdf_context[:50000]}\n"

        system_instruction = r"""
        You are Dynamo AI.
        RULES:
        1. DEFAULT: Answer in Markdown.
        2. VISUALS: Use 'graph TD' or 'xychart-beta' ONLY if asked. Wrap node text in quotes.
        3. QUIZ: Output valid JSON inside ```json_quiz ... ```.
        """
        
        full_prompt = system_instruction + "\n" + context_str + "\n"
        for msg in req.history[-6:]:
            role = msg.get('role', 'user') if isinstance(msg, dict) else getattr(msg, 'role', 'user')
            content = msg.get('content', '') if isinstance(msg, dict) else getattr(msg, 'content', '')
            full_prompt += f"{'User' if role == 'user' else 'Model'}: {content}\n"
        
        full_prompt += f"User: {req.message}\nModel:"

        active_model = gemini_model
        if req.model == "gemini-1.5-pro": active_model = genai.GenerativeModel("gemini-1.5-pro")

        response = active_model.generate_content(full_prompt)
        return {"type": "text", "content": response.text}

    except Exception as e:
        print(f"Error: {e}")
        return {"type": "text", "content": f"Error: {str(e)}"}

# --- EXPORT ENDPOINTS (NEW) ---

@app.post("/generate-word")
async def generate_word(req: ChatRequest):
    doc = Document()
    doc.add_heading('Dynamo AI Report', 0)
    for msg in req.history:
        role = msg.get('role', 'User')
        content = msg.get('content', '')
        doc.add_heading(role.capitalize(), level=1)
        doc.add_paragraph(content)
    
    byte_io = io.BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return StreamingResponse(byte_io, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=Dynamo_Report.docx"})

@app.post("/generate-ppt")
async def generate_ppt(req: ChatRequest):
    prs = Presentation()
    for msg in req.history:
        role = msg.get('role', 'User')
        content = msg.get('content', '')[:500] # Limit slide text
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        title = slide.shapes.title
        body = slide.placeholders[1]
        title.text = role.capitalize()
        body.text = content
        
    byte_io = io.BytesIO()
    prs.save(byte_io)
    byte_io.seek(0)
    return StreamingResponse(byte_io, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={"Content-Disposition": "attachment; filename=Dynamo_Presentation.pptx"})

@app.post("/generate-report") # PDF
async def generate_pdf(req: ChatRequest):
    byte_io = io.BytesIO()
    doc = SimpleDocTemplate(byte_io, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph("Dynamo AI Report", styles['Title']))
    story.append(Spacer(1, 12))
    
    for msg in req.history:
        role = msg.get('role', 'User')
        content = msg.get('content', '')
        # Simple text cleanup for PDF
        clean_content = content.replace('\n', '<br/>')
        story.append(Paragraph(f"<b>{role.capitalize()}:</b>", styles['Heading2']))
        try:
            story.append(Paragraph(clean_content, styles['Normal']))
        except:
            story.append(Paragraph("Content could not be rendered.", styles['Normal']))
        story.append(Spacer(1, 12))
        
    doc.build(story)
    byte_io.seek(0)
    return StreamingResponse(byte_io, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=Dynamo_Report.pdf"})


# --- OTHER ENDPOINTS ---
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        reader = PdfReader(file.file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return {"text": text.strip()} 
    except Exception as e:
        return {"text": "Error reading PDF."}

@app.post("/vision")
async def vision_analysis(file: UploadFile = File(...), message: str = Form("Describe this image")):
    if not gemini_model: return {"content": "Gemini Key Missing"}
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        response = gemini_model.generate_content([message, image])
        return {"content": response.text}
    except Exception: return {"content": "Error analyzing image."}

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not gemini_model: return {"text": "Gemini Key Missing"}
    try:
        temp_filename = f"temp_{int(time.time())}.wav"
        with open(temp_filename, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        uploaded_file = genai.upload_file(temp_filename)
        response = gemini_model.generate_content([uploaded_file, "Transcribe exactly."])
        os.remove(temp_filename)
        return {"text": response.text.strip()}
    except Exception: return {"text": "Error transcribing."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
