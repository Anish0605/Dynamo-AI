from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

import google.generativeai as genai
from tavily import TavilyClient

from export import router as export_router

# =========================
# APP
# =========================
app = FastAPI(title="Dynamo AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# KEYS
# =========================
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# =========================
# ROUTERS
# =========================
app.include_router(export_router)

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
def build_context(history):
    ctx = ""
    for h in history:
        if isinstance(h, dict) and "role" in h and "content" in h:
            ctx += f"{h['role'].upper()}: {h['content']}\n"
    return ctx


def gemini_answer(prompt: str, temperature: float = 0.7):
    model = genai.GenerativeModel("models/gemini-2.0-flash")
    resp = model.generate_content(
        prompt,
        generation_config={"temperature": temperature}
    )
    return resp.text


# =========================
# CHAT
# =========================
@app.post("/chat")
def chat(req: ChatReq):
    context = build_context(req.history)
    prompt = context + "\nUSER: " + req.message

    if req.use_search:
        search = tavily.search(
            query=req.message,
            max_results=5,
            include_answer=True
        )
        sources = "\n".join(
            [f"- {r['title']}: {r['url']}" for r in search.get("results", [])]
        )
        prompt += f"\n\nSOURCES:\n{sources}\n\nAnswer using sources."

    if req.deep_dive:
        temps = [0.5, 0.8, 1.1]
        answers = []
        for i, t in enumerate(temps, start=1):
            ans = gemini_answer(
                f"Perspective {i}:\n{prompt}",
                temperature=t
            )
            answers.append(ans)

        return {"type": "deep_dive", "content": answers}

    answer = gemini_answer(prompt)
    return {"type": "text", "content": answer}
