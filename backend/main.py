from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from tavily import TavilyClient
import PyPDF2
import base64
import os
import io

# ----------------------------------------
# CONFIG
# ----------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

app = FastAPI(title="Dynamo AI API")

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # In production you can restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# LLM Client (Groq API - OpenAI compatible)
client = None
if GROQ_API_KEY:
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
else:
    print("⚠️ WARNING: GROQ_API_KEY missing!")

# Tavily Search
tavily = None
if TAVILY_API_KEY:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
else:
    print("⚠️ WARNING: TAVILY_API_KEY missing!")


# ----------------------------------------
# DATA MODELS
# ----------------------------------------
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[Message] = []
    use_search: bool = True
    pdf_context: Optional[str] = None
    deep_dive: bool = False   # ⭐ frontend uses this


# ----------------------------------------
# HEALTH CHECK
# ----------------------------------------
@app.get("/")
def root():
    return {"status": "Dynamo Brain is Operational ⚡"}


# ----------------------------------------
# PDF UPLOAD → TEXT EXTRACTION
# ----------------------------------------
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        pdf = io.BytesIO(contents)
        reader = PyPDF2.PdfReader(pdf)

        text = ""
        for page in reader.pages[:10]:      # limit to 10 pages
            text += page.extract_text() or ""

        return {"text": text, "filename": file.filename}

    except Exception as e:
        raise HTTPException(500, f"PDF Error: {str(e)}")


# ----------------------------------------
# MAIN CHAT ENGINE
# ----------------------------------------
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):

    if not client:
        raise HTTPException(500, "Server error: LLM key missing.")

    try:
        # -------------------------------
        # IMAGE GENERATION TRIGGER
        # -------------------------------
        if (
            "image" in req.message.lower() and
            any(x in req.message.lower() for x in ["generate", "create", "draw", "make"])
        ):
            safe = req.message.replace(" ", "%20")
            url = f"https://image.pollinations.ai/prompt/{safe}?nologo=true"
            return {"type": "image", "content": url}

        # -------------------------------
        # CONTEXT BUILDING
        # -------------------------------
        web_context = ""

        # Tavily Search (only if enabled & no PDF context)
        if req.use_search and tavily and not req.pdf_context:
            try:
                result = tavily.search(query=req.message, search_depth="basic")
                web_context = "\n".join(
                    [item["content"] for item in result.get("results", [])]
                )
            except Exception as e:
                print("Search Error:", e)

        # Last 5 messages from history
        history_msgs = [
            {"role": m.role, "content": m.content}
            for m in req.history[-5:]
        ]

        # Deep dive mode
        detail = (
            "Reply concisely and clearly."
            if not req.deep_dive
            else "Give a deep, detailed analysis with step-by-step reasoning and examples."
        )

        # System prompt
        sys_instruction = f"""
You are Dynamo AI.

PDF CONTENT:
{req.pdf_context or "None"}

WEB CONTEXT:
{web_context or "None"}

INSTRUCTIONS:
- If PDF content is present, prioritize it.
- Otherwise use Web Context if available.
- {detail}
- Do NOT hallucinate.
- Keep answers accurate and organized.
"""

        messages = (
            [{"role": "system", "content": sys_instruction}]
            + history_msgs
            + [{"role": "user", "content": req.message}]
        )

        # -------------------------------
        # LLM CALL
        # -------------------------------
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )

        answer = response.choices[0].message.content

        return {"type": "text", "content": answer}

    except Exception as e:
        raise HTTPException(500, f"Chat Error: {str(e)}")


# ----------------------------------------
# AUDIO → TEXT (Whisper)
# ----------------------------------------
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not client:
        raise HTTPException(500, "LLM key missing.")

    try:
        contents = await file.read()

        with open("temp_audio.wav", "wb") as f:
            f.write(contents)

        with open("temp_audio.wav", "rb") as f:
            text = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="text"
            )

        os.remove("temp_audio.wav")

        return {"text": text}

    except Exception as e:
        raise HTTPException(500, f"Audio Error: {str(e)}")


# ----------------------------------------
# IMAGE → ANALYSIS (Vision Model)
# ----------------------------------------
@app.post("/vision")
async def vision(message: str = Form(...), file: UploadFile = File(...)):

    if not client:
        raise HTTPException(500, "LLM key missing.")

    try:
        file_bytes = await file.read()
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        mime = file.content_type or "image/jpeg"

        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": message},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"}
                        }
                    ]
                }
            ]
        )

        output = response.choices[0].message.content
        return {"type": "text", "content": output}

    except Exception as e:
        raise HTTPException(500, f"Vision Error: {str(e)}")
