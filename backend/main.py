import os
import io
import base64
import json
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

# A. Setup Gemini (The Brain & Eyes)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }
    # UPGRADE: Using Gemini 2.0 Flash (Advanced & Free Tier available)
    gemini_model = genai.GenerativeModel(
        model_name="gemini-2.0-flash", 
        safety_settings=safety_settings
    )
else:
    gemini_model = None
    print("WARNING: GEMINI_API_KEY is missing. Chat and Vision will fail.")

# B. Setup Groq (The Ears - Audio Transcription)
groq_client = None
if GROQ_API_KEY:
    groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

# C. Setup Tools
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
    return {"status": "Dynamo Brain (Gemini 2.0 Flash) is Active 🧠"}

# --- CHAT ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not gemini_model:
        raise HTTPException(500, "Gemini API Key Missing")
    
    try:
        # 1. Handle Image Generation commands
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean}?nologo=true"}

        # 2. Build Context
        context_str = ""
        if req.use_search and tavily and not req.pdf_context:
            try:
                print("Searching web...")
                search_result = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic")
                context_str += f"\n\n[WEB SEARCH RESULTS]:\n{search_result.get('results', [])}\n"
            except Exception as e:
                print(f"Search failed: {e}")

        if req.pdf_context:
            context_str += f"\n\n[USER UPLOADED DOCUMENT CONTEXT]:\n{req.pdf_context}\n"

        # 3. Prompt Construction
        full_prompt = "You are Dynamo AI, a helpful research assistant.\n"
        full_prompt += context_str + "\n"
        
        for msg in req.history[-6:]:
            role_label = "User" if msg.role == "user" else "Model"
            full_prompt += f"{role_label}: {msg.content}\n"
        
        full_prompt += f"User: {req.message}\nModel:"

        # 4. Generate Response
        response = gemini_model.generate_content(full_prompt)
        
        return {"type": "text", "content": response.text}

    except Exception as e:
        print(f"Gemini Chat Error: {e}")
        # Fallback error message
        return {"type": "text", "content": "I encountered an error processing that request. Please try again."}

# --- VISION ENDPOINT (Gemini 2.0 - Stable & Free) ---
@app.post("/vision")
async def vision(message: str = Form(...), file: UploadFile = File(...)):
    if not gemini_model:
        raise HTTPException(500, "Gemini API Key Missing")
    
    try:
        print(f"Gemini Vision analyzing: {file.filename}")
        
        image_bytes = await file.read()
        
        # Helper to determine mime type
        mime_type = file.content_type if file.content_type else "image/jpeg"
        
        image_part = {
            "mime_type": mime_type,
            "data": image_bytes
        }

        # Gemini 2.0 handles text + image natively
        response = gemini_model.generate_content([message, image_part])
        
        return {"type": "text", "content": response.text}

    except Exception as e:
        print(f"Gemini Vision Error: {e}")
        raise HTTPException(500, f"Vision Failed: {str(e)}")

# --- AUDIO ENDPOINT (Groq - Best for Transcription) ---
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not groq_client:
        raise HTTPException(500, "Groq API Key Missing (needed for Whisper)")
    try:
        filename = "temp_audio.wav"
        with open(filename, "wb") as f:
            f.write(await file.read())
        
        # Whisper Large V3 via Groq (Fastest)
        with open(filename, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=(filename, f.read()),
                model="whisper-large-v3-turbo",
                response_format="text"
            )
        
        return {"text": transcription}
    except Exception as e:
        print(f"Transcribe Error: {e}")
        raise HTTPException(500, str(e))

# --- UTILS ---
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        reader = PyPDF2.PdfReader(io.BytesIO(contents))
        text = ""
        for i, page in enumerate(reader.pages):
            if i > 20: break
            text += page.extract_text() or ""
        return {"text": text}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/create-razorpay-order")
async def create_order(req: OrderRequest):
    if not razorpay_client:
        raise HTTPException(500, "Payment gateway not configured")
    try:
        data = { "amount": req.amount_inr * 100, "currency": "INR", "payment_capture": 1, "notes": { "user_email": req.email } }
        order = razorpay_client.order.create(data=data)
        return { "order_id": order['id'], "amount": order['amount'], "key_id": RAZORPAY_KEY_ID }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/generate-report")
async def generate_report(req: ReportRequest):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("Dynamo AI Research Report", styles['Title']), Spacer(1, 12)]
    for msg in req.history:
        role = "User" if msg.role == 'user' else "Dynamo AI"
        story.append(Paragraph(f"<b>{role}:</b> {msg.content}", styles['BodyText']))
        story.append(Spacer(1, 12))
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=report.pdf"})
