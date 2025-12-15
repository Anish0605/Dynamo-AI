import os
import io
import base64
import json
import re
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# --- NEW BRAIN: Google Gemini ---
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- AUDIO ENGINE: Groq (via OpenAI client) ---
from openai import OpenAI

# --- DOCUMENT ENGINES ---
from docx import Document
from pptx import Presentation 
from pptx.util import Inches, Pt

# --- UTILS ---
from tavily import TavilyClient
import PyPDF2
import razorpay
from supabase import create_client, Client

# PDF Report Generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ==========================================
# 1. CONFIGURATION & KEYS
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ==========================================
# 2. CLIENT INITIALIZATION
# ==========================================

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }
    gemini_model = genai.GenerativeModel(model_name="gemini-2.0-flash", safety_settings=safety_settings)
else:
    gemini_model = None
    print("WARNING: GEMINI_API_KEY is missing.")

groq_client = None
if GROQ_API_KEY:
    groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

tavily = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)) if RAZORPAY_KEY_ID else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) if SUPABASE_URL else None

# ==========================================
# 3. FASTAPI APP SETUP
# ==========================================
app = FastAPI(title="Dynamo AI - Gemini 2.0 Powered")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []
    use_search: bool = True
    pdf_context: Optional[str] = None 
    deep_dive: bool = False
    model: str = "gemini-2.0-flash" 

class OrderRequest(BaseModel):
    amount_inr: int
    email: str

class ReportRequest(BaseModel):
    history: List[Message]

# ==========================================
# 4. ENDPOINTS
# ==========================================

@app.get("/")
def health_check():
    return {"status": "Dynamo Brain (Gemini 2.0) is Active 🧠"}

# --- CHAT ENDPOINT (Strict Syntax Fix) ---
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
        if req.use_search and tavily and not req.pdf_context:
            try:
                res = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic")
                context_str += f"\n\n[WEB]:\n{res.get('results', [])}\n"
            except: pass
        if req.pdf_context: context_str += f"\n\n[DOC]:\n{req.pdf_context}\n"

        # 3. System Prompt (STRICT QUOTING RULE)
        system_instruction = """
        You are Dynamo AI.
        If the user asks to 'visualize', 'map', 'chart', or 'draw':
        1. Explain briefly.
        2. Generate a Mermaid.js diagram wrapped in ```mermaid ... ```.
        3. RULE: Use 'graph TD'. 
        4. CRITICAL RULE: Wrap ALL label text in double quotes to prevent syntax errors.
           CORRECT: A["Artificial Intelligence (AI)"]
           WRONG: A[Artificial Intelligence (AI)]
        Example:
        ```mermaid
        graph TD
          A["Main Topic"] --> B["Sub-topic (Details)"]
          A --> C["Another Branch"]
        ```
        """
        
        full_prompt = system_instruction + "\n" + context_str + "\n"
        for msg in req.history[-6:]:
            full_prompt += f"{'User' if msg.role == 'user' else 'Model'}: {msg.content}\n"
        full_prompt += f"User: {req.message}\nModel:"

        response = gemini_model.generate_content(full_prompt)
        return {"type": "text", "content": response.text}

    except Exception as e:
        return {"type": "text", "content": "Error processing request."}

# --- VISION ---
@app.post("/vision")
async def vision(message: str = Form(...), file: UploadFile = File(...)):
    if not gemini_model: raise HTTPException(500, "Gemini Key Missing")
    try:
        img_data = await file.read()
        mime = file.content_type if file.content_type else "image/jpeg"
        response = gemini_model.generate_content([message, {"mime_type": mime, "data": img_data}])
        return {"type": "text", "content": response.text}
    except Exception as e:
        raise HTTPException(500, str(e))

# --- AUDIO ---
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not groq_client: raise HTTPException(500, "Groq Key Missing")
    try:
        with open("temp.wav", "wb") as f: f.write(await file.read())
        with open("temp.wav", "rb") as f:
            tx = groq_client.audio.transcriptions.create(file=("temp.wav", f.read()), model="whisper-large-v3-turbo", response_format="text")
        return {"text": tx}
    except Exception as e: raise HTTPException(500, str(e))

# --- DOC EXPORTS ---

@app.post("/generate-word")
async def generate_word(req: ReportRequest):
    try:
        doc = Document()
        doc.add_heading('Dynamo AI Report', 0)
        for msg in req.history:
            doc.add_heading("User" if msg.role == 'user' else "Dynamo", level=2)
            doc.add_paragraph(msg.content.replace("**", ""))
            doc.add_paragraph("-" * 20)
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=dynamo.docx"})
    except Exception as e: raise HTTPException(500, str(e))

# --- PPT EXPORT ---
@app.post("/generate-ppt")
async def generate_ppt(req: ReportRequest):
    if not gemini_model: raise HTTPException(500, "Gemini Key Missing")
    try:
        # 1. Ask Gemini to summarize the chat into JSON
        chat_text = "\n".join([f"{m.role}: {m.content}" for m in req.history])
        ppt_prompt = f"""
        Analyze this conversation and convert it into a PowerPoint structure.
        Return ONLY valid JSON. No markdown formatting.
        Format:
        [
          {{ "title": "Slide Title", "bullets": ["Point 1", "Point 2"] }},
          {{ "title": "Next Slide", "bullets": ["Point A", "Point B"] }}
        ]
        Conversation: {chat_text}
        """
        
        # Force JSON response from Gemini
        resp = gemini_model.generate_content(ppt_prompt)
        clean_json = resp.text.replace("```json", "").replace("```", "").strip()
        slides_data = json.loads(clean_json)

        # 2. Build PPT
        prs = Presentation()
        for slide_info in slides_data:
            slide_layout = prs.slide_layouts[1] # Bullet layout
            slide = prs.slides.add_slide(slide_layout)
            
            # Title
            if slide.shapes.title:
                slide.shapes.title.text = slide_info.get("title", "Untitled")
            
            # Bullets
            if slide.placeholders[1]:
                tf = slide.placeholders[1].text_frame
                tf.text = slide_info.get("bullets", [])[0] if slide_info.get("bullets") else ""
                for bullet in slide_info.get("bullets", [])[1:]:
                    p = tf.add_paragraph()
                    p.text = bullet
                    p.level = 0

        buffer = io.BytesIO()
        prs.save(buffer)
        buffer.seek(0)
        
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={"Content-Disposition": "attachment; filename=dynamo_slides.pptx"})

    except Exception as e:
        print(f"PPT Error: {e}")
        # Fallback if AI fails to give JSON
        raise HTTPException(500, "Failed to generate slides. Try simpler chat content.")

# --- UTILS ---
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        reader = PyPDF2.PdfReader(io.BytesIO(contents))
        text = "".join([p.extract_text() or "" for p in reader.pages[:20]])
        return {"text": text}
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/create-razorpay-order")
async def create_order(req: OrderRequest):
    if not razorpay_client: raise HTTPException(500, "Payment Config Missing")
    try:
        order = razorpay_client.order.create(data={"amount": req.amount_inr * 100, "currency": "INR", "payment_capture": 1, "notes": {"email": req.email}})
        return {"order_id": order['id'], "amount": order['amount'], "key_id": RAZORPAY_KEY_ID}
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/generate-report")
async def generate_report(req: ReportRequest):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = [Paragraph("Dynamo Report", getSampleStyleSheet()['Title'])]
    for m in req.history: story.append(Paragraph(f"<b>{m.role}:</b> {m.content}", getSampleStyleSheet()['BodyText'])); story.append(Spacer(1, 12))
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=report.pdf"})
