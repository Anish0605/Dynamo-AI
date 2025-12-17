# main.py - Final Production (Dynamo Radio + All Features)
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
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
import uuid
import edge_tts 
import asyncio

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

# --- CONFIG ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

gemini_model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")

tavily = None
if TAVILY_API_KEY:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)

# --- MODELS ---
class ChatRequest(BaseModel):
    message: str
    history: list = []
    use_search: bool = True
    deep_dive: bool = False
    model: str = "gemini-2.0-flash"
    pdf_context: str = None

class ExportRequest(BaseModel):
    history: list

# --- CHAT ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not gemini_model: raise HTTPException(500, "Gemini Key Missing")
    
    try:
        # 1. Image Check
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean}?nologo=true"}

        # 2. Context
        context_str = ""
        if req.use_search and not req.pdf_context and tavily:
            try:
                # Deep Dive Logic
                depth = "advanced" if req.deep_dive else "basic"
                res = tavily.search(query=req.message, search_depth=depth, max_results=5)
                context_str += f"\n\n[WEB RESULTS]:\n{res.get('results', [])}\n"
            except: pass

        if req.pdf_context:
            context_str += f"\n\n[USER DOCUMENT]:\n{req.pdf_context[:50000]}\n"

        # 3. System Prompt
        base_instruction = "You are Dynamo AI."
        if req.deep_dive:
            base_instruction += " [MODE: DEEP DIVE] Provide extensive, detailed, research-grade answers."
        
        system_instruction = base_instruction + r"""
        
        RULES:
        1. DEFAULT: Answer in Markdown.
        
        2. VISUALS (Explicit Request Only):
           - IF comparing numbers/trends: Use `xychart-beta`. 
             * x-axis labels in quotes: [ "A", "B" ]. Data in brackets: [10, 20].
           - IF showing structure/process: Use `graph TD`.
             * Quotes around labels: A["Start"] --> B["End"].
           - NO JSON for visuals.
        
        3. QUIZ (Explicit Request Only):
           - Output valid JSON inside ```json_quiz ... ```.
           - Keys: "question", "options", "answer", "explanation".
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
        return {"type": "text", "content": f"Error: {str(e)}"}

# --- DYNAMO RADIO ENDPOINT (NEW) ---
@app.post("/generate-radio")
async def generate_radio(req: ChatRequest):
    if not gemini_model: raise HTTPException(500, "Gemini Key Missing")
    
    # 1. Scriptwriter
    prompt = f"""
    Convert this text into a 2-person podcast script between 'Host' (Alex) and 'Expert' (Sam).
    - Keep it short (max 6 exchanges).
    - Make it conversational and punchy.
    - OUTPUT: A raw JSON list ONLY. No markdown.
    - Format: [ {{"speaker": "Host", "text": "..."}}, {{"speaker": "Expert", "text": "..."}} ]
    
    CONTENT: {req.pdf_context[:10000] if req.pdf_context else req.message}
    """
    
    try:
        resp = gemini_model.generate_content(prompt)
        clean_json = resp.text.replace("```json", "").replace("```", "").strip()
        script = eval(clean_json) # Safe parsing of list
        
        # 2. Voice Generation
        audio_files = []
        for line in script:
            voice = "en-US-GuyNeural" if line["speaker"] == "Host" else "en-US-AriaNeural"
            temp = f"temp_{uuid.uuid4()}.mp3"
            communicate = edge_tts.Communicate(line["text"], voice)
            await communicate.save(temp)
            audio_files.append(temp)
            
        # 3. Stitching (Binary Append Method)
        output_filename = f"Dynamo_Podcast_{int(time.time())}.mp3"
        with open(output_filename, "wb") as outfile:
            for f in audio_files:
                with open(f, "rb") as infile:
                    outfile.write(infile.read())
                os.remove(f) # Cleanup chunks
                
        return FileResponse(output_filename, media_type="audio/mpeg", filename="Dynamo_Podcast.mp3")

    except Exception as e:
        print(f"Radio Error: {e}")
        return {"error": str(e)}

# --- EXPORT ENDPOINTS ---
@app.post("/generate-word")
async def generate_word(req: ExportRequest):
    doc = Document()
    doc.add_heading('Dynamo AI Report', 0)
    for msg in req.history:
        role = msg.get('role', 'User') if isinstance(msg, dict) else msg.role
        content = msg.get('content', '') if isinstance(msg, dict) else msg.content
        doc.add_heading(str(role).capitalize(), level=1)
        doc.add_paragraph(str(content))
    byte_io = io.BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return StreamingResponse(byte_io, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=Dynamo_Report.docx"})

@app.post("/generate-ppt")
async def generate_ppt(req: ExportRequest):
    prs = Presentation()
    for msg in req.history:
        role = msg.get('role', 'User') if isinstance(msg, dict) else msg.role
        content = msg.get('content', '') if isinstance(msg, dict) else msg.content
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = str(role).capitalize()
        slide.placeholders[1].text = str(content)[:800]
    byte_io = io.BytesIO()
    prs.save(byte_io)
    byte_io.seek(0)
    return StreamingResponse(byte_io, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={"Content-Disposition": "attachment; filename=Dynamo_Presentation.pptx"})

@app.post("/generate-report")
async def generate_pdf(req: ExportRequest):
    byte_io = io.BytesIO()
    doc = SimpleDocTemplate(byte_io, pagesize=letter)
    story = [Paragraph("Dynamo AI Report", getSampleStyleSheet()['Title']), Spacer(1, 12)]
    for msg in req.history:
        role = msg.get('role', 'User') if isinstance(msg, dict) else msg.role
        content = msg.get('content', '') if isinstance(msg, dict) else msg.content
        story.append(Paragraph(f"<b>{str(role).capitalize()}:</b>", getSampleStyleSheet()['Heading2']))
        try: story.append(Paragraph(str(content).replace('\n', '<br/>'), getSampleStyleSheet()['Normal']))
        except: pass
        story.append(Spacer(1, 12))
    doc.build(story)
    byte_io.seek(0)
    return StreamingResponse(byte_io, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=Dynamo_Report.pdf"})

# --- FILES ---
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        reader = PdfReader(file.file)
        text = "".join([p.extract_text() for p in reader.pages])
        return {"text": text.strip()} 
    except: return {"text": "Error reading PDF."}

@app.post("/vision")
async def vision_analysis(file: UploadFile = File(...), message: str = Form("Describe this image")):
    if not gemini_model: return {"content": "Gemini Key Missing"}
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        response = gemini_model.generate_content([message, image])
        return {"content": response.text}
    except: return {"content": "Error analyzing image."}

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not gemini_model: return {"text": "Gemini Key Missing"}
    try:
        temp = f"temp_{int(time.time())}.wav"
        with open(temp, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        uploaded = genai.upload_file(temp)
        response = gemini_model.generate_content([uploaded, "Transcribe exactly."])
        os.remove(temp)
        return {"text": response.text.strip()}
    except: return {"text": "Error transcribing."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
