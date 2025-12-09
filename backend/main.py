# main.py
import os
import io
import json
import base64
import hmac
import hashlib
from datetime import date

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict

import PyPDF2
import razorpay

# Optional LLM clients (these may be missing - keep defensive guards)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from tavily import TavilyClient
except Exception:
    TavilyClient = None

# Supabase client
from supabase import create_client, Client as SupabaseClient

# Firebase admin
import firebase_admin
from firebase_admin import credentials as firebase_credentials, auth as firebase_auth

# ---------- CONFIG (from Render env vars) ----------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

PORT = int(os.getenv("PORT", "10000"))

# ---------- INIT ----------
app = FastAPI(title="Dynamo AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LLM and search clients (optional)
client = None
tavily = None
if GROQ_API_KEY and OpenAI:
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
if TAVILY_API_KEY and TavilyClient:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)

# Supabase (backend-only service_role client)
supabase: Optional[SupabaseClient] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Razorpay client
razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Firebase Admin initialization
if FIREBASE_SERVICE_ACCOUNT_JSON:
    try:
        cred_json = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
        cred = firebase_credentials.Certificate(cred_json)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print("Firebase init error:", e)

# ---------- Pydantic models ----------
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []
    use_search: bool = True
    pdf_context: Optional[str] = None
    deep_dive: bool = False

class CreateOrderRequest(BaseModel):
    amount_inr: int  # eg 99 or 499

# ---------- Auth dependency ----------
async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict:
    """
    Verifies Firebase ID token passed in Authorization: Bearer <token>.
    Returns decoded token (contains uid, email).
    """
    if not FIREBASE_SERVICE_ACCOUNT_JSON:
        raise HTTPException(status_code=500, detail="Auth not configured on server")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    id_token = authorization.split(" ", 1)[1]
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded
    except Exception as e:
        print("Firebase token verify error:", e)
        raise HTTPException(status_code=401, detail="Invalid auth token")

# ---------- Supabase helpers ----------
def get_or_create_user(firebase_uid: str, email: Optional[str]):
    if not supabase:
        return None
    try:
        q = supabase.table("users").select("*").eq("firebase_uid", firebase_uid).limit(1).execute()
        rows = q.data or []
        if rows:
            return rows[0]
        ins = supabase.table("users").insert({
            "firebase_uid": firebase_uid,
            "email": email or "",
            "plan": "free",
            "daily_quota_used": 0,
            "quota_date": None
        }).execute()
        return ins.data[0]
    except Exception as e:
        print("Supabase get/create user error:", e)
        return None

def log_chat_to_supabase(user_id: Optional[str], user_msg: str, assistant_msg: str):
    if not supabase or not user_id:
        return
    try:
        title = user_msg.strip()[:80]
        chat_res = supabase.table("chats").insert({
            "user_id": user_id,
            "title": title
        }).execute()
        chat_id = chat_res.data[0]["id"]
        supabase.table("messages").insert([
            {"chat_id": chat_id, "role": "user", "content": user_msg},
            {"chat_id": chat_id, "role": "assistant", "content": assistant_msg}
        ]).execute()
    except Exception as e:
        print("Supabase log error:", e)

def enforce_plan_and_quota(user_row: Dict, req: ChatRequest):
    """
    Mutates req.use_search / req.deep_dive for free users.
    Increments daily_quota_used. Raises HTTPException if quota exceeded.
    """
    if not supabase or not user_row:
        return "unknown"
    uid = user_row.get("id")
    plan = user_row.get("plan", "free")
    quota_date = user_row.get("quota_date")
    quota_used = user_row.get("daily_quota_used") or 0
    today_str = date.today().isoformat()

    if quota_date != today_str:
        quota_used = 0
        quota_date = today_str

    if plan == "free":
        # disable advanced modes
        req.use_search = False
        req.deep_dive = False
        if quota_used >= 10:
            raise HTTPException(status_code=402, detail="Daily free limit reached. Upgrade to Plus.")
    # increment usage by 1 for this response
    quota_used += 1
    try:
        supabase.table("users").update({
            "quota_date": quota_date,
            "daily_quota_used": quota_used
        }).eq("id", uid).execute()
    except Exception as e:
        print("Supabase update quota error:", e)
    return plan

# ---------- Endpoints ----------
@app.get("/")
def health_check():
    return {"status": "Dynamo Brain is Operational ⚡"}

# Upload PDF (extract text)
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
        raise HTTPException(status_code=500, detail=f"PDF Error: {e}")

# Transcribe audio (whisper via Groq/OpenAI client if configured)
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...), user=Depends(get_current_user)):
    if not client:
        raise HTTPException(500, "Transcription service not configured")
    try:
        with open("temp_audio.wav", "wb") as f:
            f.write(await file.read())
        with open("temp_audio.wav", "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo", file=f, response_format="text"
            )
        os.remove("temp_audio.wav")
        return {"text": transcription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Vision endpoint (image analysis)
@app.post("/vision")
async def vision_analysis(message: str = Form(...), file: UploadFile = File(...), user=Depends(get_current_user)):
    if not client:
        raise HTTPException(500, "Vision service not configured")
    try:
        contents = await file.read()
        base64_image = base64.b64encode(contents).decode("utf-8")
        mime_type = file.content_type or "image/jpeg"
        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": message},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                ]
            }]
        )
        return {"type": "text", "content": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Create Razorpay order (frontend calls this; backend returns order_id and key_id)
@app.post("/create-razorpay-order")
async def create_razorpay_order(body: CreateOrderRequest, user=Depends(get_current_user)):
    if not razorpay_client:
        raise HTTPException(status_code=500, detail="Razorpay not configured")
    firebase_uid = user.get("uid")
    email = user.get("email")
    try:
        order = razorpay_client.order.create({
            "amount": body.amount_inr * 100,
            "currency": "INR",
            "payment_capture": 1,
            "notes": {"firebase_uid": firebase_uid, "email": email or ""}
        })
        return {"order_id": order["id"], "key_id": RAZORPAY_KEY_ID, "amount": body.amount_inr * 100}
    except Exception as e:
        print("Razorpay create order error:", e)
        raise HTTPException(status_code=500, detail="Unable to create order")

# Razorpay webhook (configured in Razorpay Dashboard)
@app.post("/razorpay/webhook")
async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    if not signature or not RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Missing signature or webhook secret")

    # Verify HMAC-SHA256 signature
    computed = hmac.new(
        bytes(RAZORPAY_WEBHOOK_SECRET, "utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    # Razorpay's header is base64 of hex? Many docs expect:
    # compare computed hex to header directly or handle differences. We'll compare hex.
    if signature != computed:
        # As fallback, try the Razorpay utility if available (not required).
        print("Webhook signature mismatch. header:", signature, "computed:", computed)
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(body)
    event = payload.get("event")

    if event == "payment.captured":
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        notes = payment.get("notes", {})
        firebase_uid = notes.get("firebase_uid")
        email = notes.get("email")
        # mark user as paid
        try:
            if supabase and firebase_uid:
                supabase.table("users").update({"plan": "plus"}).eq("firebase_uid", firebase_uid).execute()
            print("Upgraded user to plus:", firebase_uid or email)
        except Exception as e:
            print("Failed to upgrade user:", e)
    return {"status": "ok"}

# CHAT endpoint (requires auth)
@app.post("/chat")
async def chat_endpoint(req: ChatRequest, user=Depends(get_current_user)):
    if not client:
        raise HTTPException(500, "LLM not configured")
    firebase_uid = user.get("uid")
    email = user.get("email")
    user_row = get_or_create_user(firebase_uid, email)
    try:
        plan = enforce_plan_and_quota(user_row, req)
    except HTTPException:
        raise

    try:
        # quick image shortcut
        if "image" in req.message.lower() and any(k in req.message.lower() for k in ["generate", "create", "draw"]):
            clean = req.message.replace(" ", "%20")
            img_url = f"https://image.pollinations.ai/prompt/{clean}?nologo=true"
            # log minimal
            log_chat_to_supabase(user_row.get("id") if user_row else None, req.message, img_url)
            return {"type": "image", "content": img_url, "plan": plan}

        # search context
        context_text = ""
        if req.use_search and tavily and not req.pdf_context:
            try:
                res = tavily.search(query=req.message, search_depth="basic")
                context_text = "\n".join([r.get("content", "") for r in res.get("results", [])])
            except Exception as e:
                print("Tavily search error:", e)

        history_messages = [{"role": m.role, "content": m.content} for m in req.history[-5:]]
        sys_instruction = f"""
        You are Dynamo AI.
        PDF CONTENT: {req.pdf_context or 'None'}
        WEB CONTEXT: {context_text}

        INSTRUCTIONS:
        - If PDF content is present, answer based on that.
        - Otherwise, use Web Context.
        - Be helpful, concise, and accurate.
        """
        messages = [{"role": "system", "content": sys_instruction}] + history_messages + [{"role": "user", "content": req.message}]

        response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
        answer = response.choices[0].message.content

        # log
        log_chat_to_supabase(user_row.get("id") if user_row else None, req.message, answer)

        return {"type": "text", "content": answer, "plan": plan}
    except Exception as e:
        print("Chat error:", e)
        raise HTTPException(status_code=500, detail=str(e))
