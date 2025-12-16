# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import google.generativeai as genai
from tavily import TavilyClient
from dotenv import load_dotenv
import shutil
import time

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API KEYS ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# --- INIT CLIENTS ---
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
        
        # Web Search logic
        if req.use_search and not req.pdf_context:
            if tavily:
                try:
                    # print("🔍 Searching Web...") 
                    depth = "advanced" if req.deep_dive else "basic"
                    res = tavily.search(query=req.message, search_depth=depth, max_results=3)
                    context_str += f"\n\n[WEB SEARCH RESULTS]:\n{res.get('results', [])}\n"
                except Exception as e:
                    print(f"Tavily Error: {e}")
            else:
                print("⚠️ Search requested but TAVILY_API_KEY not set.")

        if req.pdf_context:
            context_str += f"\n\n[DOCUMENT CONTEXT]:\n{req.pdf_context[:20000]}\n"

        # 3. System Prompt
        system_instruction = r"""
        You are Dynamo AI.
        RULES:
        1. DEFAULT: Answer naturally in Markdown.
        2. VISUALS: If asked for a "map", "chart", or "flow", use Mermaid.js.
        3. QUIZ: If asked for a quiz, output valid JSON inside ```json_quiz ... ``` blocks. No real newlines in strings.
        """
        
        full_prompt = system_instruction + "\n" + context_str + "\n"
        for msg in req.history[-6:]:
            role = msg.get('role', 'user') if isinstance(msg, dict) else getattr(msg, 'role', 'user')
            content = msg.get('content', '') if isinstance(msg, dict) else getattr(msg, 'content', '')
            full_prompt += f"{'User' if role == 'user' else 'Model'}: {content}\n"
        
        full_prompt += f"User: {req.message}\nModel:"

        active_model = gemini_model
        if req.model == "gemini-1.5-pro":
             active_model = genai.GenerativeModel("gemini-1.5-pro")

        response = active_model.generate_content(full_prompt)
        return {"type": "text", "content": response.text}

    except Exception as e:
        print(f"Backend Error: {e}")
        return {"type": "text", "content": f"Error: {str(e)}"}

# --- REAL VOICE TRANSCRIPTION (FIXED) ---
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not gemini_model: return {"text": "Error: Gemini Key Missing"}
    
    try:
        # 1. Save temp file
        temp_filename = f"temp_{int(time.time())}.wav"
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Upload to Gemini
        print(f"🎙️ Transcribing {temp_filename}...")
        uploaded_file = genai.upload_file(temp_filename)
        
        # 3. Generate Transcript
        response = gemini_model.generate_content([uploaded_file, "Transcribe this audio exactly as spoken."])
        
        # 4. Cleanup
        os.remove(temp_filename)
        
        return {"text": response.text.strip()}
    except Exception as e:
        print(f"Transcription Error: {e}")
        return {"text": "Error transcribing audio."}

# --- Placeholders ---
@app.post("/upload-pdf")
async def upload_pdf(): return {"text": "PDF Upload Placeholder"} # Update this if you have the PDF logic ready
@app.post("/vision")
async def vision_analysis(): return {"content": "Image Analysis Placeholder"} # Update this if needed

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
