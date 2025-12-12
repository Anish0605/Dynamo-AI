from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from tavily import TavilyClient
import PyPDF2
import base64
import os
import io
import razorpay
import json
from supabase import create_client, Client

# PDF Generation Imports
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

app = FastAPI(title="Dynamo AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CLIENTS ---
client = None
tavily = None
razorpay_client = None
supabase: Client = None

if GROQ_API_KEY:
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
if TAVILY_API_KEY:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# --- MODELS ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []
    use_search: bool = True
    pdf_context: Optional[str] = None 
    deep_dive: bool = False
    model: str = "llama-3.3-70b-versatile"

class OrderRequest(BaseModel):
    amount_inr: int
    email: str

class ReportRequest(BaseModel):
    history: List[Message]

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "Dynamo Brain is Operational ⚡"}

# 1. CREATE PAYMENT
@app.post("/create-razorpay-order")
async def create_order(req: OrderRequest):
    if not razorpay_client:
        raise HTTPException(500, "Payment gateway not configured")
    try:
        data = { 
            "amount": req.amount_inr * 100, 
            "currency": "INR", 
            "payment_capture": 1,
            "notes": { "user_email": req.email }
        }
        order = razorpay_client.order.create(data=data)
        return { "order_id": order['id'], "amount": order['amount'], "key_id": RAZORPAY_KEY_ID }
    except Exception as e:
        raise HTTPException(500, str(e))

# 2. WEBHOOK
@app.post("/razorpay/webhook")
async def razorpay_webhook(request: Request):
    if not supabase:
        return {"status": "error"}
    try:
        body = await request.body()
        signature = request.headers.get('X-Razorpay-Signature')
        razorpay_client.utility.verify_webhook_signature(body.decode('utf-8'), signature, RAZORPAY_WEBHOOK_SECRET)
        event = await request.json()
        if event['event'] == 'payment.captured':
            payment = event['payload']['payment']['entity']
            email = payment.get('notes', {}).get('user_email') or payment.get('email')
            if email:
                supabase.table("users").update({"plan": "plus"}).eq("email", email).execute()
        return {"status": "ok"}
    except Exception:
        raise HTTPException(500, "Webhook Error")

# 3. PDF REPORT
@app.post("/generate-report")
async def generate_report(req: ReportRequest):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("Dynamo AI Research Report", styles['Title']), Spacer(1, 12)]
    
    for msg in req.history:
        role = "User Query" if msg.role == 'user' else "Dynamo Insight"
        style = styles['Heading3'] if msg.role == 'user' else styles['Heading4']
        story.append(Paragraph(f"<b>{role}:</b>", style))
        content = msg.content.replace("**", "").replace("\n", "<br/>")
        story.append(Paragraph(content, styles['BodyText']))
        story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=report.pdf"})

# 4. CHAT (Multi-Model)
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not client:
        raise HTTPException(500, "LLM Key Missing")
    try:
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean}?nologo=true"}

        context = ""
        if req.use_search and tavily and not req.pdf_context:
            try:
                res = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic")
                context = "\n".join([r['content'] for r in res.get('results', [])])
            except:
                pass

        sys_instruction = f"You are Dynamo AI. PDF: {req.pdf_context or 'None'} WEB: {context}"
        messages = [{"role": "system", "content": sys_instruction}]
        for msg in req.history[-5:]:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": req.message})
        
        response = client.chat.completions.create(model=req.model, messages=messages)
        return {"type": "text", "content": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(500, str(e))

# 5. UPLOAD PDF
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        reader = PyPDF2.PdfReader(io.BytesIO(contents))
        text = "".join([page.extract_text() or "" for page in reader.pages[:10]])
        return {"text": text}
    except Exception as e:
        raise HTTPException(500, str(e))

# 6. VISION
@app.post("/vision")
async def vision(message: str = Form(...), file: UploadFile = File(...)):
    if not client:
        raise HTTPException(500, "Key Missing")
    try:
        b64 = base64.b64encode(await file.read()).decode('utf-8')
        res = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[{"role":"user","content":[{"type":"text","text":message},{"type":"image_url","image_url":{"url":f"data:{file.content_type};base64,{b64}"}}]}]
        )
        return {"type":"text","content":res.choices[0].message.content}
    except Exception as e:
        raise HTTPException(500, str(e))

# 7. TRANSCRIBE (Fixed Syntax Error)
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not client:
        raise HTTPException(500, "Key Missing")
    try:
        # Save temp file
        with open("t.wav", "wb") as f:
            f.write(await file.read())
        
        # Transcribe
        with open("t.wav", "rb") as f:
            tx = client.audio.transcriptions.create(model="whisper-large-v3-turbo", file=f, response_format="text")
        
        return {"text": tx}
    except Exception as e:
        raise HTTPException(500, str(e))
