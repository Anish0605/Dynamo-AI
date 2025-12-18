# main.py - Unified Production (Groq + Smart Analyst + Radio + All Features)
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os, io, shutil, time, uuid, base64, asyncio
import google.generativeai as genai
from groq import Groq
from tavily import TavilyClient
from dotenv import load_dotenv
from pypdf import PdfReader
from PIL import Image
import pandas as pd
import matplotlib.pyplot as plt

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
    model: str = "gemini-2.0-flash"
    pdf_context: str = None

class ExportRequest(BaseModel):
    history: list

# --- CORE CHAT LOGIC ---
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        # 1. Image Gen
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean}?nologo=true"}

        # 2. Context Building
        context_str = ""
        if req.use_search and not req.pdf_context and tavily:
            try:
                res = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic", max_results=5)
                context_str += f"\n\n[WEB]:\n{res.get('results', [])}\n"
            except: pass
        if req.pdf_context:
            context_str += f"\n\n[DOC]:\n{req.pdf_context[:50000]}\n"

        sys_msg = "You are Dynamo AI. Rules: 1. Markdown only. 2. Charts use xychart-beta (labels in quotes). 3. Flowcharts use graph TD (labels in quotes). 4. Quizzes use ```json_quiz block."
        if req.deep_dive: sys_msg += " [DEEP DIVE] Provide exhaustive, detailed research answers."

        # 3. Model Routing
        if "llama3" in req.model:
            if not groq_client: return {"type": "text", "content": "Groq Key Missing"}
            msgs = [{"role": "system", "content": sys_msg}]
            if context_str: msgs.append({"role": "system", "content": f"Context: {context_str}"})
            for m in req.history[-6:]:
                msgs.append({"role": "user" if m.get('role') == 'user' else "assistant", "content": m.get('content', '')})
            msgs.append({"role": "user", "content": req.message})
            
            completion = groq_client.chat.completions.create(messages=msgs, model=req.model)
            return {"type": "text", "content": completion.choices[0].message.content}
        else:
            model = genai.GenerativeModel("gemini-2.0-flash-exp") if req.model == "gemini-2.0-flash" else genai.GenerativeModel("gemini-1.5-pro")
            prompt = f"{sys_msg}\n{context_str}\n" + "\n".join([f"{'User' if m.get('role') == 'user' else 'AI'}: {m.get('content')}" for m in req.history[-6:]]) + f"\nUser: {req.message}\nAI:"
            response = model.generate_content(prompt)
            return {"type": "text", "content": response.text}
    except Exception as e: return {"type": "text", "content": f"Error: {str(e)}"}

# --- SMART ANALYST (CSV/EXCEL) ---
@app.post("/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents)) if file.filename.endswith('.csv') else pd.read_excel(io.BytesIO(contents))
        num_cols = df.select_dtypes(include=['number']).columns.tolist()
        txt_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
        if not num_cols: return {"error": "No numeric data found."}
        
        plt.figure(figsize=(10, 6))
        chart_df = df.head(15)
        x, y = (txt_cols[0] if txt_cols else chart_df.index.name), num_cols[0]
        plt.bar(chart_df[x].astype(str), chart_df[y], color='#EAB308')
        plt.title(f"{y} by {x}"); plt.xticks(rotation=45); plt.tight_layout()
        
        buf = io.BytesIO(); plt.savefig(buf, format='png'); buf.seek(0); plt.close()
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        
        insight_prompt = f"Analyze summary and give 1 punchy business insight (max 20 words): {df.describe().to_string()}"
        insight = genai.GenerativeModel("gemini-2.0-flash-exp").generate_content(insight_prompt).text
        return {"image": f"data:image/png;base64,{img_b64}", "insight": insight}
    except Exception as e: return {"error": str(e)}

# --- DYNAMO RADIO ---
@app.post("/generate-radio")
async def generate_radio(req: ChatRequest):
    prompt = f"Convert to 2-person podcast script (Alex/Sam). JSON list ONLY. exchange max 6. Content: {req.pdf_context[:10000] if req.pdf_context else req.message}"
    try:
        resp = genai.GenerativeModel("gemini-2.0-flash-exp").generate_content(prompt)
        script = eval(resp.text.replace("```json", "").replace("```", "").strip())
        audio_files = []
        for line in script:
            v = "en-US-GuyNeural" if line["speaker"] == "Host" or line["speaker"] == "Alex" else "en-US-AriaNeural"
            tmp = f"temp_{uuid.uuid4()}.mp3"
            await edge_tts.Communicate(line["text"], v).save(tmp)
            audio_files.append(tmp)
        out = f"Radio_{int(time.time())}.mp3"
        with open(out, "wb") as f_out:
            for f in audio_files:
                with open(f, "rb") as f_in: f_out.write(f_in.read())
                os.remove(f)
        return FileResponse(out, media_type="audio/mpeg")
    except Exception as e: return {"error": str(e)}

# (Keep your existing /generate-word, /generate-ppt, /generate-report, /upload-pdf, /vision, /transcribe endpoints exactly as they were...)
