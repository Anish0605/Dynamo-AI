from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# RAZORPAY & SUPABASE KEYS
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

# --- INITIALIZATION ---
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

class OrderRequest(BaseModel):
    amount_inr: int

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "Dynamo Brain is Operational ⚡"}

# 1. CREATE PAYMENT ORDER
@app.post("/create-razorpay-order")
async def create_order(req: OrderRequest):
    if not razorpay_client:
        raise HTTPException(500, "Payment gateway not configured")
    try:
        data = { "amount": req.amount_inr * 100, "currency": "INR", "payment_capture": 1 }
        order = razorpay_client.order.create(data=data)
        return { "order_id": order['id'], "amount": order['amount'], "key_id": RAZORPAY_KEY_ID }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 2. WEBHOOK (UPGRADE USER)
@app.post("/razorpay/webhook")
async def razorpay_webhook(request: Request):
    if not supabase: return {"status": "error", "message": "DB config missing"}
    try:
        body = await request.body()
        signature = request.headers.get('X-Razorpay-Signature')
        razorpay_client.utility.verify_webhook_signature(body.decode('utf-8'), signature, RAZORPAY_WEBHOOK_SECRET)

        event = await request.json()
        if event['event'] == 'payment.captured':
            payment = event['payload']['payment']['entity']
            user_email = payment.get('email')
            if user_email:
                print(f"💰 Upgrading plan for {user_email}")
                supabase.table("users").update({"plan": "plus"}).eq("email", user_email).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

# 3. PDF PARSER
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        pdf_file = io.BytesIO(contents)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages[:10]:
            text += page.extract_text() or ""
        return {"text": text, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. VISION
@app.post("/vision")
async def vision_analysis(message: str = Form(...), file: UploadFile = File(...)):
    if not client: raise HTTPException(500, "Server Error: LLM Key Missing")
    try:
        contents = await file.read()
        base64_image = base64.b64encode(contents).decode('utf-8')
        mime_type = file.content_type or "image/jpeg"
        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[{"role": "user", "content": [{"type": "text", "text": message}, {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}]}]
        )
        return {"type": "text", "content": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 5. TRANSCRIBE
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not client: raise HTTPException(500, "Server Error: LLM Key Missing")
    try:
        with open("temp_audio.wav", "wb") as buffer: buffer.write(await file.read())
        with open("temp_audio.wav", "rb") as f:
            transcription = client.audio.transcriptions.create(model="whisper-large-v3-turbo", file=f, response_format="text")
        os.remove("temp_audio.wav")
        return {"text": transcription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 6. CHAT
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not client: raise HTTPException(500, "Server Error: LLM Key Missing")
    try:
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean}?nologo=true"}

        context = ""
        if req.use_search and tavily and not req.pdf_context:
            try:
                res = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic")
                context = "\n".join([r['content'] for r in res.get('results', [])])
            except: pass

        sys_instruction = f"You are Dynamo AI. PDF: {req.pdf_context or 'None'} WEB: {context}"
        messages = [{"role": "system", "content": sys_instruction}]
        for msg in req.history[-5:]: messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": req.message})
        
        response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
        return {"type": "text", "content": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
