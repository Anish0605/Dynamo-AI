# main.py - Fixed for Mermaid Syntax & Quiz Keys
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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

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
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean}?nologo=true"}

        context_str = ""
        if req.use_search and not req.pdf_context and tavily:
            try:
                res = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic", max_results=3)
                context_str += f"\n\n[WEB]:\n{res.get('results', [])}\n"
            except: pass

        if req.pdf_context:
            context_str += f"\n\n[DOC]:\n{req.pdf_context[:20000]}\n"

        # --- SYSTEM PROMPT (FIXED) ---
        system_instruction = r"""
        You are Dynamo AI.
        
        RULES:
        1. DEFAULT: Answer in Markdown.
        
        2. VISUALS (Mermaid.js):
           - Use 'graph TD' for maps/processes.
           - CRITICAL: You MUST wrap ALL node text in double quotes.
             CORRECT: A["Solar System"] --> B["Earth"]
             WRONG: A[Solar System] --> B[Earth]
        
        3. QUIZ MODE:
           - Output valid JSON inside ```json_quiz ... ```.
           - keys MUST be lowercase: "question", "options", "answer", "explanation".
           - "answer" must be an integer index (0, 1, 2, 3).
           
           Example:
           ```json_quiz
           [
             {"question": "Smallest planet?", "options": ["Mars", "Mercury"], "answer": 1, "explanation": "Mercury is smallest."}
           ]
           ```
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
        print(f"Error: {e}")
        return {"type": "text", "content": f"Error: {str(e)}"}

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not gemini_model: return {"text": "Gemini Key Missing"}
    try:
        temp_filename = f"temp_{int(time.time())}.wav"
        with open(temp_filename, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        uploaded_file = genai.upload_file(temp_filename)
        response = gemini_model.generate_content([uploaded_file, "Transcribe exactly."])
        os.remove(temp_filename)
        return {"text": response.text.strip()}
    except Exception: return {"text": "Error transcribing."}

@app.post("/upload-pdf")
async def upload_pdf(): return {"text": "PDF placeholder"}
@app.post("/vision")
async def vision_analysis(): return {"content": "Vision placeholder"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
