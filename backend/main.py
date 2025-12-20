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

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """You are Dynamo AI, the #1 AI Research OS made in India. 
Rules:
1. Always identify as Dynamo AI.
2. Use Markdown only.
3. For Charts, use Mermaid 'xychart-beta'.
4. For Flowcharts/Mindmaps, use Mermaid 'graph TD' or 'mindmap'.
5. [DEEP DIVE]: If requested, provide 3 distinct perspectives: Technical, Practical, and Future.
6. [QUIZ]: If asked for a quiz, use the format [QUIZ_START] ... [QUIZ_END] with JSON content.
7. [FACT CHECK]: If requested, verify claims and provide a confidence score.
"""

# --- CORE CHAT LOGIC ---
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        msg_lower = req.message.lower()
        
        # 1. Identity Interceptor
        if any(q in msg_lower for q in ["who are you", "what is your name", "your name"]):
            return {"type": "text", "content": "My name is **Dynamo AI**, the #1 AI Research OS made in India. I am built for high-end research and data analysis."}

        # 2. Image Generation Redirect
        if "image" in msg_lower and ("generate" in msg_lower or "create" in msg_lower):
            clean = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean}?nologo=true&width=1024&height=1024"}

        # 3. Web Search & Context Building
        context_str = ""
        if req.use_search and not req.pdf_context and tavily:
            try:
                res = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic", max_results=5)
                context_str += f"\n\n[RESEARCH DATA]:\n{res.get('results', [])}\n"
            except: pass
        if req.pdf_context:
            context_str += f"\n\n[UPLOADED DOCUMENT]:\n{req.pdf_context[:40000]}\n"

        # 4. Mode Handling
        final_instruction = SYSTEM_PROMPT
        if req.deep_dive:
            final_instruction += "\n[MODE: DEEP DIVE] Provide three exhaustive perspectives: 1. Academic/Technical 2. Industry/Practical 3. Future Trends."
        if req.fact_check:
            final_instruction += "\n[MODE: FACT CHECK] Analyze the user's claim for accuracy. Provide a Truth Score (0-100%) and verify against sources."

        # 5. Model Routing
        if "llama3" in req.model:
            if not groq_client: return {"type": "text", "content": "Groq API Key is missing on the server."}
            msgs = [{"role": "system", "content": final_instruction}]
            if context_str: msgs.append({"role": "system", "content": f"Context: {context_str}"})
            for m in req.history[-6:]:
                msgs.append({"role": "user" if m.get('role') == 'user' else "assistant", "content": m.get('content', '')})
            msgs.append({"role": "user", "content": req.message})
            
            completion = groq_client.chat.completions.create(messages=msgs, model=req.model)
            return {"type": "text", "content": completion.choices[0].message.content}
        else:
            model = genai.GenerativeModel(req.model if "gemini" in req.model else "gemini-2.0-flash")
            prompt_parts = [f"{final_instruction}\n{context_str}\n"]
            for m in req.history[-6:]:
                role = "User" if m.get('role') == 'user' else "AI"
                prompt_parts.append(f"{role}: {m.get('content')}")
            prompt_parts.append(f"User: {req.message}\nAI:")
            
            response = model.generate_content("\n".join(prompt_parts))
            return {"type": "text", "content": response.text}
    except Exception as e:
        return {"type": "text", "content": f"Dynamo Engine Error: {str(e)}"}

# --- SMART ANALYST (CSV/EXCEL) ---
@app.post("/analyze-file")
async def analyze_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents)) if file.filename.endswith('.csv') else pd.read_excel(io.BytesIO(contents))
        num_cols = df.select_dtypes(include=['number']).columns.tolist()
        if not num_cols: return {"error": "No numeric data found for visualization."}
        
        plt.figure(figsize=(10, 6))
        df.head(15).plot(kind='bar', color='#EAB308')
        plt.title("Data Trends Analysis"); plt.tight_layout()
        
        buf = io.BytesIO(); plt.savefig(buf, format='png'); buf.seek(0); plt.close()
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        
        insight_prompt = f"Analyze this data summary and provide one brilliant business insight (max 15 words): {df.describe().to_string()}"
        insight = genai.GenerativeModel("gemini-2.0-flash").generate_content(insight_prompt).text
        return {"image": f"data:image/png;base64,{img_b64}", "insight": insight}
    except Exception as e: return {"error": str(e)}

# --- DYNAMO RADIO (2-Person Script) ---
@app.post("/generate-radio")
async def generate_radio(req: ChatRequest):
    prompt = f"Create a short 2-person podcast script between Alex and Sam. Return valid JSON only: [{{'speaker': 'Alex', 'text': '... '}}, ...]. Content: {req.message}"
    try:
        resp = genai.GenerativeModel("gemini-2.0-flash").generate_content(prompt)
        # Clean the response to ensure valid JSON
        clean_json = resp.text.strip().replace("```json", "").replace("```", "")
        script = json.loads(clean_json)
        
        audio_files = []
        for line in script:
            voice = "en-IN-PrabhatNeural" if line["speaker"] == "Alex" else "en-IN-AnanyaNeural"
            tmp = f"temp_{uuid.uuid4()}.mp3"
            await edge_tts.Communicate(line["text"], voice).save(tmp)
            audio_files.append(tmp)
        
        out_filename = f"Radio_{int(time.time())}.mp3"
        with open(out_filename, "wb") as f_out:
            for f in audio_files:
                with open(f, "rb") as f_in: f_out.write(f_in.read())
                os.remove(f)
        return FileResponse(out_filename, media_type="audio/mpeg")
    except Exception as e: return {"error": f"Radio Error: {str(e)}"}

# --- EXPORT ENDPOINTS ---
@app.post("/generate-word")
async def generate_word(req: ExportRequest):
    doc = Document()
    doc.add_heading('Dynamo AI Research Report', 0)
    for m in req.history:
        p = doc.add_paragraph()
        p.add_run(f"{'User' if m['role']=='user' else 'Dynamo AI'}: ").bold = True
        p.add_run(m['content'])
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=Dynamo_Report.docx"})

@app.post("/generate-ppt")
async def generate_ppt(req: ExportRequest):
    prs = Presentation()
    for m in req.history[-4:]: # Top 4 exchanges
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = "Research Insight"
        slide.placeholders[1].text = m['content'][:500]
    buf = io.BytesIO(); prs.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={"Content-Disposition": "attachment; filename=Dynamo_Presentation.pptx"})

@app.post("/generate-report")
async def generate_pdf(req: ExportRequest):
    buf = io.BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    content = [Paragraph("Dynamo AI - Research Summary", styles['Title']), Spacer(1, 12)]
    for m in req.history:
        content.append(Paragraph(f"<b>{'User' if m['role']=='user' else 'AI'}:</b>", styles['Normal']))
        content.append(Paragraph(m['content'], styles['Normal']))
        content.append(Spacer(1, 12))
    pdf.build(content); buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=Dynamo_Report.pdf"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
