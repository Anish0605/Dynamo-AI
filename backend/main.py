from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests, os
from export import router as export_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(export_router)

GEMINI_KEY = os.getenv("GEMINI_API_KEY")

class ChatReq(BaseModel):
    message: str
    model: str = "gemini-2.0-flash"
    deep_dive: bool = False
    search: bool = False

def gemini(prompt, model):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
    payload = {"contents":[{"parts":[{"text":prompt}]}]}
    r = requests.post(url, json=payload)
    try:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "No response"

@app.post("/chat")
def chat(req: ChatReq):
    if not req.deep_dive:
        return {"reply": gemini(req.message, req.model)}

    answers = []
    for i in range(3):
        answers.append(gemini(f"Perspective {i+1}: {req.message}", req.model))

    return {
        "reply": "\n\n---\n\n".join(answers)
    }
