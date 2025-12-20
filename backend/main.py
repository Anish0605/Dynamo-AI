from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, io

import google.generativeai as genai
from tavily import TavilyClient

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from docx import Document
from pptx import Presentation
from export import router as export_router

# =========================
# APP
# =========================
app = FastAPI(title="Dynamo AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OK for now
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(export_router)

# =========================
# KEYS
# =========================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
tavily = TavilyClient(api_key=TAVILY_API_KEY)

# =========================
# SCHEMA
# =========================
class ChatReq(BaseModel):
    message: str
    history: list = []
    use_search: bool = False
    deep_dive: bool = False
    model: str = "gemini-2.0-flash"

# =========================
# ROOT
# =========================
@app.get("/")
def root():
    return {"message": "Dynamo AI backend running"}

# =========================
# HELPERS
# =========================
def gemini_answer(prompt: str, temperature: float = 0.7):
    model = genai.GenerativeModel("models/gemini-2.0-flash")
    resp = model.generate_content(
        prompt,
        generation_config={"temperature": temperature}
    )
    return resp.text

def build_context(history):
    ctx = ""
    for h in history:
        if isinstance(h, dict) and "role" in h and "content" in h:
            ctx += f"{h['role'].upper()}: {h['content']}\n"
    return ctx

# =========================
# CHAT
# =========================
@app.post("/chat")
def chat(req: ChatReq):
    try:
        context = build_context(req.history)
        prompt = context + "\nUSER: " + req.message

        # ---- Web Search (only if toggle ON)
        if req.use_search:
            search = tavily.search(
                query=req.message,
                max_results=5,
                include_answer=True
            )
            sources = "\n".join(
                [f"- {r['title']}: {r['url']}" for r in search.get("results", [])]
            )
            prompt += f"\n\nWEB SOURCES:\n{sources}\n\nAnswer using the sources above."

        # ---- DeepDive (3 answers)
        if req.deep_dive:
            answers = []
            temps = [0.5, 0.8, 1.1]
            for i, t in enumerate(temps, start=1):
                a = gemini_answer(
                    f"Provide perspective {i}.\n{prompt}",
                    temperature=t
                )
                answers.append(a)
            return {"type": "deep_dive", "content": answers}

        # ---- Normal
        out = gemini_answer(prompt, temperature=0.7)
        return {"type": "text", "content": out}

    except Exception as e:
        return {"type": "error", "content": str(e)}

# =========================
# EXPORTS
# =========================
@app.post("/export/pdf")
def export_pdf(text: str = Body(..., embed=True)):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf)
    styles = getSampleStyleSheet()
    doc.build([Paragraph(text.replace("\n", "<br/>"), styles["Normal"])])
    return {"file": buf.getvalue().hex()}

@app.post("/export/docx")
def export_docx(text: str = Body(..., embed=True)):
    d = Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return {"file": buf.getvalue().hex()}

@app.post("/export/pptx")
def export_pptx(text: str = Body(..., embed=True)):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Dynamo AI"
    slide.placeholders[1].text = text[:4000]
    buf = io.BytesIO()
    prs.save(buf)
    return {"file": buf.getvalue().hex()}
