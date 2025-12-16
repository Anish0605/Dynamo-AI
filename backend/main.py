# main.py
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
    # Default to Flash for speed
    gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")

tavily = None
if TAVILY_API_KEY:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)

# --- REQUEST MODELS ---
class ChatRequest(BaseModel):
    message: str
    history: list = []
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
        # 1. Image Generation Check
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean_prompt = req.message.replace(" ", "%20")
            # Pollinations AI for free image generation
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean_prompt}?nologo=true"}

        # 2. Build Context
        context_str = ""
        
        # A. Web Search (Tavily)
        if req.use_search and tavily and not req.pdf_context:
            try:
                print("🔍 Searching Tavily...")
                search_depth = "advanced" if req.deep_dive else "basic"
                res = tavily.search(query=req.message, search_depth=search_depth, max_results=3)
                context_str += f"\n\n[REAL-TIME WEB DATA]:\n{res.get('results', [])}\n"
            except Exception as e:
                print(f"Search Error: {e}")

        # B. PDF Context
        if req.pdf_context:
            context_str += f"\n\n[USER UPLOADED DOCUMENT]:\n{req.pdf_context[:20000]}\n" # Limit char count

        # 3. System Prompt (Strict JSON & Visuals)
        # We use a RAW string (r"") to ensure backslashes are handled correctly in Python
        system_instruction = r"""
        You are Dynamo AI.
        
        CORE BEHAVIOR:
        1. DEFAULT: Answer naturally in Markdown.
        2. VISUALS: If asked to "visualize", "map", or "chart", use Mermaid.js (graph TD or xychart-beta).
        
        3. *** QUIZ MODE (CRITICAL STRICT RULES) ***
           If the user asks for a "quiz", "test", or "practice":
           - You MUST output the data inside a ```json_quiz``` block.
           - THE JSON MUST BE VALID.
           - CRITICAL: Do NOT use real newlines inside the strings. Use '\n' literal.
           - CRITICAL: Escape all double quotes inside strings (e.g., "print(\"Hello\")").
           
           Target Format:
           ```json_quiz
           [
             {
               "question": "What is the result of 2 + 2?",
               "options": ["3", "4", "5", "22"],
               "answer": 1, 
               "explanation": "2 plus 2 equals 4."
             }
           ]
           ```
           - 'answer' must be the numeric index (0, 1, 2, 3).
           - Generate 3-5 questions.
        """
        
        # 4. Construct History
        full_prompt = system_instruction + "\n" + context_str + "\n"
        for msg in req.history[-6:]: # Keep last 6 turns
            full_prompt += f"{'User' if msg.role == 'user' else 'Model'}: {msg.content}\n"
        
        full_prompt += f"User: {req.message}\nModel:"

        # 5. Select Model Version
        active_model = gemini_model
        if req.model == "gemini-1.5-pro":
             active_model = genai.GenerativeModel("gemini-1.5-pro")

        # 6. Generate
        response = active_model.generate_content(full_prompt)
        return {"type": "text", "content": response.text}

    except Exception as e:
        print(f"Backend Error: {e}")
        return {"type": "text", "content": f"I encountered an error: {str(e)}"}

# --- FILE UPLOADS (Stubbed for completeness) ---
@app.post("/upload-pdf")
async def upload_pdf(): return {"text": "PDF extraction placeholder"}

@app.post("/vision")
async def vision_analysis(): return {"content": "Image analysis placeholder"}

@app.post("/transcribe")
async def transcribe_audio(): return {"text": "Audio transcription placeholder"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
