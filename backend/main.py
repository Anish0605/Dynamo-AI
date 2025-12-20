from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os

from groq import Groq

# =========================
# APP SETUP
# =========================
app = FastAPI(title="Dynamo AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OK for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# GROQ CLIENT
# =========================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

SUPPORTED_MODELS = {
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile"
}

DEFAULT_MODEL = "llama-3.1-8b-instant"

# =========================
# REQUEST SCHEMA
# =========================
class ChatRequest(BaseModel):
    message: str
    history: list = []
    use_search: bool = False
    deep_dive: bool = False
    model: str = DEFAULT_MODEL


# =========================
# ROOT (OPTIONAL)
# =========================
@app.get("/")
def root():
    return {"message": "Dynamo AI backend running"}


# =========================
# CHAT ENDPOINT
# =========================
@app.post("/chat")
def chat(req: ChatRequest):
    try:
        model = req.model if req.model in SUPPORTED_MODELS else DEFAULT_MODEL

        messages = []

        # Add history if exists
        for h in req.history:
            if "role" in h and "content" in h:
                messages.append({
                    "role": h["role"],
                    "content": h["content"]
                })

        # Add user message
        messages.append({
            "role": "user",
            "content": req.message
        })

        # Deep Dive mode (3 answers)
        if req.deep_dive:
            responses = []
            for i in range(3):
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7 + (i * 0.2)
                )
                responses.append(
                    completion.choices[0].message.content
                )

            return {
                "type": "deep_dive",
                "content": responses
            }

        # Normal chat
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )

        return {
            "type": "text",
            "content": completion.choices[0].message.content
        }

    except Exception as e:
        return {
            "type": "error",
            "content": f"Dynamo Engine Error: {str(e)}"
        }
