#main.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import models, search, vision, voice, export, analyzer, processor

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ChatReq(BaseModel):
    message: str
    history: list = []
    use_search: bool = True
    deep_dive: bool = False
    model: str = "gemini-2.0-flash"

@app.post("/chat")
async def chat(req: ChatReq):
    msg = req.message.lower()
    # Image Routing
    if "image" in msg and ("create" in msg or "generate" in msg):
        prompt = req.message.replace("generate image of", "").replace("create image of", "").strip()
        return await vision.generate_image_base64(prompt)
    
    # Context & AI Routing
    ctx = search.get_web_context(req.message, req.deep_dive) if req.use_search else ""
    response = models.get_ai_response(req.message, req.history, req.model, ctx)
    return {"type": "text", "content": response}

@app.post("/generate-radio")
async def radio(req: ChatReq):
    return await voice.generate_voice_stream(req.message)

@app.post("/generate-word")
async def word_exp(req: dict): return export.word(req['history'])

@app.post("/generate-ppt")
async def ppt_exp(req: dict): return export.ppt(req['history'])

@app.post("/generate-report")
async def pdf_exp(req: dict): return export.pdf(req['history'])

if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
