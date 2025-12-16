# main.py - Final Fixed Version
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import google.generativeai as genai
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Enable CORS
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

# --- REQUEST MODEL ---
class ChatRequest(BaseModel):
    message: str
    history: list = []  # Defaults to empty list
    use_search: bool = True
    deep_dive: bool = False
    model: str = "gemini-2.0-flash"
    pdf_context: str = None

# --- CHAT ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not gemini_model: 
        raise HTTPException(500, "Gemini Key Missing")
    
    try:
        # 1. Image Check
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean_prompt = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean_prompt}?nologo=true"}

        # 2. Context Building
        context_str = ""
        
        # Web Search
        if req.use_search and tavily and not req.pdf_context:
            try:
                print("🔍 Searching Tavily...")
                search_depth = "advanced" if req.deep_dive else "basic"
                res = tavily.search(query=req.message, search_depth=search_depth, max_results=3)
                context_str += f"\n\n[WEB RESULTS]:\n{res.get('results', [])}\n"
            except Exception as e:
                print(f"Search Error: {e}")

        # PDF Context
        if req.pdf_context:
            context_str += f"\n\n[DOCUMENT CONTEXT]:\n{req.pdf_context[:20000]}\n"

        # 3. System Prompt (Quiz & Visuals)
        system_instruction = r"""
        You are Dynamo AI.
        
        RULES:
        1. DEFAULT: Answer naturally in Markdown.
        2. VISUALS: If asked for a "map", "chart", or "flow", use Mermaid.js code blocks (graph TD or xychart-beta).
        
        3. *** QUIZ MODE ***
           If the user asks for a quiz/test:
           - Output a ```json_quiz``` block.
           - NO NEWLINES inside JSON strings. Use \n instead.
           - FORMAT:
           ```json_quiz
           [
             {"question": "Q1 text?", "options": ["A", "B", "C", "D"], "answer": 0, "explanation": "Exp text."}
           ]
           ```
           - 'answer' must be the index number (0, 1, 2, 3).
        """
        
        # 4. Construct History (THE FIX IS HERE)
        full_prompt = system_instruction + "\n" + context_str + "\n"
        
        for msg in req.history[-6:]:
            # FIX: We now check if it's a dictionary OR an object to prevent the crash
            role = msg.get('role', 'user') if isinstance(msg, dict) else getattr(msg, 'role', 'user')
            content = msg.get('content', '') if isinstance(msg, dict) else getattr(msg, 'content', '')
            
            full_prompt += f"{'User' if role == 'user' else 'Model'}: {content}\n"
        
        full_prompt += f"User: {req.message}\nModel:"

        # 5. Model Selection & Generation
        active_model = gemini_model
        if req.model == "gemini-1.5-pro":
             active_model = genai.GenerativeModel("gemini-1.5-pro")

        response = active_model.generate_content(full_prompt)
        return {"type": "text", "content": response.text}

    except Exception as e:
        print(f"Backend Crash: {e}") # This will show in Render logs
        return {"type": "text", "content": f"System Error: {str(e)}"}

# --- STUB ENDPOINTS (Required for frontend to not break) ---
@app.post("/upload-pdf")
async def upload_pdf(): return {"text": "PDF Upload Placeholder"}

@app.post("/vision")
async def vision_analysis(): return {"content": "Image Analysis Placeholder"}

@app.post("/transcribe")
async def transcribe_audio(): return {"text": "Transcription Placeholder"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
