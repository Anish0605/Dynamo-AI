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

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

app = FastAPI(title="Dynamo AI API")

# CORS: allow your frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later you can change to ["https://dynamoai.in"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CLIENT INITIALIZATION ---
client = None
tavily = None

if GROQ_API_KEY:
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
else:
    print("⚠️ WARNING: GROQ_API_KEY not found.")

if TAVILY_API_KEY:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
else:
    print("⚠️ WARNING: TAVILY_API_KEY not found.")

# --- DATA MODELS ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = None
    use_search: bool = True
    pdf_context: Optional[str] = None  # Text extracted from PDF


# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "Dynamo Brain is Operational ⚡"}


# 1. PDF PARSER
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Extracts text from uploaded PDF."""
    try:
        contents = await file.read()
        pdf_file = io.BytesIO(contents)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        # Limit to first 10 pages to prevent token overflow
        for page in reader.pages[:10]:
            text += page.extract_text() or ""
        return {"text": text, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF Error: {str(e)}")


# 2. MAIN CHAT ENGINE
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not client:
        raise HTTPException(status_code=500, detail="Server Error: LLM Key Missing")

    try:
        # A. IMAGE GENERATION TRIGGER
        if (
            "image" in req.message.lower()
            and (
                "generate" in req.message.lower()
                or "create" in req.message.lower()
                or "draw" in req.message.lower()
            )
        ):
            clean = req.message.replace(" ", "%20")
            img_url = f"https://image.pollinations.ai/prompt/{clean}?nologo=true"
            return {"type": "image", "content": img_url}

        # B. SEARCH LOGIC
        context = ""
        if req.use_search and tavily and not req.pdf_context:
            try:
                print(f"Searching for: {req.message}")
                res = tavily.search(query=req.message, search_depth="basic")
                context = "\n".join(r["content"] for r in res.get("results", []))
            except Exception as e:
                print(f"Search Error: {e}")

        # C. HISTORY CONTEXT (keep last 5 turns)
        history_messages: List[dict] = []
        if req.history:
            for msg in req.history[-5:]:
                history_messages.append({"role": msg.role, "content": msg.content})

        # D. SYSTEM PROMPT
        sys_instruction = f"""
        You are Dynamo AI.
        PDF CONTENT: {req.pdf_context if req.pdf_context else "None"}
        WEB CONTEXT: {context}

        INSTRUCTIONS:
        - If PDF content is present, answer based on that.
        - Otherwise, use Web Context if available.
        - Be helpful, concise, and accurate.
        """

        # E. LLM CALL
        messages = (
            [{"role": "system", "content": sys_instruction}]
            + history_messages
            + [{"role": "user", "content": req.message}]
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
        )
        answer = response.choices[0].message.content

        return {"type": "text", "content": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 3. VOICE TRANSCRIPTION (Whisper)
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=500, detail="Server Error: LLM Key Missing")

    try:
        # Save temp file (Groq/OpenAI client wants a file handle)
        tmp_path = "temp_audio.wav"
        with open(tmp_path, "wb") as buffer:
            buffer.write(await file.read())

        with open(tmp_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="text",
            )

        os.remove(tmp_path)
        return {"text": transcription}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 4. VISION (IMAGE ANALYSIS)
@app.post("/vision")
async def vision_analysis(message: str = Form(...), file: UploadFile = File(...)):
    if not client:
        raise HTTPException(status_code=500, detail="Server Error: LLM Key Missing")

    try:
        contents = await file.read()
        base64_image = base64.b64encode(contents).decode("utf-8")
        mime_type = file.content_type or "image/jpeg"

        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": message},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
        )
        return {"type": "text", "content": response.choices[0].message.content}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
