from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from openai import OpenAI
from tavily import TavilyClient
import PyPDF2
import json
import base64
import os
import io

# --- CONFIGURATION ---
# In production (Render/Railway), set these as Environment Variables.
# For local testing, you can paste keys here, but DO NOT commit keys to GitHub.
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

app = FastAPI(title="Dynamo AI API")

# Setup CORS (Allows your HTML website to talk to this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change to ["https://dynamoai.in"] in production for security
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
    history: List[Message] = []
    use_search: bool = True
    pdf_context: Optional[str] = None # Text extracted from PDF

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "Dynamo Brain is Operational ⚡"}

# 1. PDF PARSER
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Extracts text from uploaded PDF"""
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
    if not client: raise HTTPException(500, "Server Error: LLM Key Missing")

    try:
        # A. IMAGE GENERATION TRIGGER
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower() or "draw" in req.message.lower()):
            clean = req.message.replace(" ", "%20")
            img_url = f"https://image.pollinations.ai/prompt/{clean}?nologo=true"
            return {"type": "image", "content": img_url}

        # B. SEARCH LOGIC
        context = ""
        # Only search if enabled AND no PDF is active (prioritize document chat)
        if req.use_search and tavily and not req.pdf_context:
            try:
                print(f"Searching for: {req.message}")
                res = tavily.search(query=req.message, search_depth="basic")
                context = "\n".join([r['content'] for r in res.get('results', [])])
            except Exception as e:
                print(f"Search Error: {e}")

        # C. HISTORY CONTEXT
        # We use the history sent from the frontend
        history_messages = []
        for msg in req.history[-5:]: # Keep last 5 turns
            history_messages.append({"role": msg.role, "content": msg.content})

        # D. PROMPT ENGINEERING
        sys_instruction = f"""
        You are Dynamo AI.
        PDF CONTENT: {req.pdf_context if req.pdf_context else "None"}
        WEB CONTEXT: {context}
        
        INSTRUCTIONS:
        - If PDF content is present, answer based on that.
        - Otherwise, use Web Context.
        - Be helpful, concise, and accurate.
        """
        
        # E. INFERENCE
        messages = [{"role": "system", "content": sys_instruction}] + history_messages + [{"role": "user", "content": req.message}]
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        answer = response.choices[0].message.content

        return {"type": "text", "content": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. VOICE TRANSCRIPTION (Whisper)
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not client: raise HTTPException(500, "Server Error: LLM Key Missing")
    try:
        # Save temp file because Groq client needs a file on disk/buffer with name
        with open("temp_audio.wav", "wb") as buffer:
            buffer.write(await file.read())
        
        with open("temp_audio.wav", "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo", 
                file=f, 
                response_format="text"
            )
        
        # Cleanup
        os.remove("temp_audio.wav")
        return {"text": transcription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. VISION (IMAGE ANALYSIS)
@app.post("/vision")
async def vision_analysis(message: str = Form(...), file: UploadFile = File(...)):
    if not client: raise HTTPException(500, "Server Error: LLM Key Missing")

    try:
        # Read and Encode Image
        contents = await file.read()
        base64_image = base64.b64encode(contents).decode('utf-8')
        mime_type = file.content_type or "image/jpeg"
        
        # Call Vision Model
        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview", # Updated to active model
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
