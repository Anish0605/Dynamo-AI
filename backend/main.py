# main.py - Unified Production (Groq + Gemini + Smart Analyst + Radio + Exports)
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os, io, shutil, time, uuid, base64, asyncio, json
import google.generativeai as genai
from groq import Groq
from tavily import TavilyClient
from dotenv import load_dotenv
from pypdf import PdfReader
from PIL import Image
import pandas as pd
import matplotlib.pyplot as plt
import aiohttp

# Report Imports
from docx import Document
from pptx import Presentation
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
import edge_tts

load_dotenv()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- CONFIG ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")

genai.configure(api_key=GEMINI_KEY) if GEMINI_KEY else None
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
tavily = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None

class ChatRequest(BaseModel):
    message: str
    history: list = []
    use_search: bool = True
    deep_dive: bool = False
    fact_check: bool = False
    model: str = "gemini-2.0-flash"
    pdf_context: str = None

class ExportRequest(BaseModel):
    history: list

SYSTEM_PROMPT = """You are Dynamo AI, the #1 AI Research OS made in India. 
Rules:
1. Always identify as Dynamo AI.
2. Use Markdown only.
3. For Flowcharts, use Mermaid graph TD syntax inside ```mermaid blocks.
4. For Quizzes, use JSON inside ```json_quiz blocks.
5. [DEEP DIVE]: If requested, provide 3 sections: Technical, Practical, and Future.
"""

# --- CORE CHAT LOGIC ---
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        msg_lower = req.message.lower()
        
        # Identity Check
        if any(q in msg_lower for q in ["who are you", "your name", "what is your name"]):
            return {"type": "text", "content": "My name is **Dynamo AI**, the #1 AI Research OS made in India. I specialize in deep research and data analysis."}

        # 1. Image Generation (Base64 for Download)
        if "image" in msg_lower and ("generate" in msg_lower or "create" in msg_lower):
            prompt = req.message.replace("generate image of", "").replace("create image of", "").strip()
            image_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?nologo=true"
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        b64 = base64.b64encode(img_data).decode('utf-8')
                        return {"type": "image_v2", "content": f"data:image/jpeg;base64,{b64}", "prompt": prompt}

        # 2. Context & Search
        context_str = ""
        if req.use_search and not req.pdf_context and tavily:
            try:
                res = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic")
                context_str += f"\n\n[WEB SEARCH]:\n{res.get('results', [])}\n"
            except: pass
        if req.pdf_context:
            context_str += f"\n\n[DOCUMENT]:\n{req.pdf_context[:40000]}\n"

        # 3. Model Prompting
        mode_instr = ""
        if req.deep_dive: mode_instr = "\n[DEEP DIVE] Exhaustive analysis across Technical, Practical, and Future perspectives."
        if req.fact_check: mode_instr = "\n[FACT CHECK] Verify claim accuracy with a truth score."

        full_prompt = f"{SYSTEM_PROMPT}{mode_instr}\n{context_str}\nUser: {req.message}\nAI:"

        if "llama3" in req.model and groq_client:
            completion = groq_client.chat.completions.create(messages=[{"role": "user", "content": full_prompt}], model=req.model)
            return {"type": "text", "content": completion.choices[0].message.content}
        else:
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(full_prompt)
            return {"type": "text", "content": response.text}

    except Exception as e:
        return {"type": "text", "content": f"Engine Error: {str(e)}"}

# --- SMART ANALYST ---
@app.post("/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents)) if file.filename.endswith('.csv') else pd.read_excel(io.BytesIO(contents))
        plt.figure(figsize=(10, 6)); df.head(15).plot(kind='bar', color='#EAB308'); plt.tight_layout()
        buf = io.BytesIO(); plt.savefig(buf, format='png'); buf.seek(0); plt.close()
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        return {"image": f"data:image/png;base64,{img_b64}", "insight": "Analysis complete. Trends visualized."}
    except Exception as e: return {"error": str(e)}

# --- DYNAMO RADIO ---
@app.post("/generate-radio")
async def generate_radio(req: ChatRequest):
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"Create a 2-person podcast script (Alex/Sam) about: {req.message}. JSON only: [{{'speaker': 'Alex', 'text': '...'}}]"
        resp = model.generate_content(prompt)
        clean_json = resp.text.strip().replace("```json", "").replace("```", "")
        script = json.loads(clean_json)
        audio_files = []
        for line in script[:6]:
            voice = "en-IN-PrabhatNeural" if line["speaker"] == "Alex" else "en-IN-AnanyaNeural"
            tmp = f"{uuid.uuid4()}.mp3"
            await edge_tts.Communicate(line["text"], voice).save(tmp)
            audio_files.append(tmp)
        out = f"Radio_{int(time.time())}.mp3"
        with open(out, "wb") as f_out:
            for f in audio_files:
                with open(f, "rb") as f_in: f_out.write(f_in.read())
                os.remove(f)
        return FileResponse(out, media_type="audio/mpeg")
    except Exception as e: return {"error": str(e)}

# --- EXPORTS ---
@app.post("/generate-word")
async def generate_word(req: ExportRequest):
    doc = Document(); doc.add_heading('Dynamo AI Research Report', 0)
    for m in req.history: doc.add_paragraph(f"{'User' if m['role']=='user' else 'AI'}: {m['content']}")
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
