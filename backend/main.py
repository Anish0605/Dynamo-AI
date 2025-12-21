# main.py - The Central Router
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os

# 1. IMPORT SECTION - Filenames must match exactly on GitHub
import config
import model
import search
import image
import voice
import export
import analysis  # The Universal Engine
import supabase_client

app = FastAPI(title="Dynamo AI Hub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatReq(BaseModel):
    message: str
    history: list = []
    use_search: bool = True
    deep_dive: bool = False
    model: str = "gemini-2.0-flash"

@app.get("/")
async def health():
    return {"status": "online", "identity": "Dynamo AI"}

@app.post("/chat")
async def chat(req: ChatReq):
    msg_lower = req.message.lower()
    
    # Image Generation Routing
    if any(k in msg_lower for k in ["generate image", "create image"]):
        prompt = req.message.split("of")[-1].strip() if "of" in msg_lower else req.message
        return await image.generate_image_base64(prompt)
    
    context = ""
    if req.use_search:
        context = search.get_web_context(req.message, req.deep_dive)
    
    response = model.get_ai_response(req.message, req.history, req.model, context)
    return {"type": "text", "content": response}

@app.post("/analyze-data")
async def analyze_data(file: UploadFile = File(...)):
    """
    Universal Intelligence Endpoint:
    Routes any file to the analysis.py universal engine.
    """
    contents = await file.read()
    # Combined logic: Handles Excel, PDF, and Vision
    return analysis.process_file_universally(contents, file.filename)

@app.post("/generate-radio")
async def radio(req: ChatReq):
    return await voice.generate_voice_stream(req.message)

# Export Routes
@app.post("/generate-word")
async def word_exp(req: dict): return export.word(req.get('history', []))
@app.post("/generate-ppt")
async def ppt_exp(req: dict): return export.ppt(req.get('history', []))
@app.post("/generate-report")
async def pdf_exp(req: dict): return export.pdf(req.get('history', []))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
