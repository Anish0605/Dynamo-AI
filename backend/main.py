#main.py - The Central Router
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os

# Import Modular Engines matching your GitHub names exactly
import config
import model             
import search            
import image             
import voice             
import export            
import analysis          
import pdf               
import supabase_client   

app = FastAPI(title="Dynamo AI Hub")

# Production CORS setup
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
    
    # 1. Image Routing (image.py)
    if "image" in msg_lower and ("create" in msg_lower or "generate" in msg_lower):
        prompt = req.message.replace("generate image of", "").replace("create image of", "").strip()
        return await image.generate_image_base64(prompt)
    
    # 2. Web Research Logic (search.py)
    ctx = ""
    if req.use_search:
        try:
            ctx = search.get_web_context(req.message, req.deep_dive)
        except:
            ctx = ""
    
    # 3. Model Logic (model.py)
    try:
        response = model.get_ai_response(req.message, req.history, req.model, ctx)
        return {"type": "text", "content": response}
    except Exception as e:
        return {"type": "text", "content": f"⚠️ Dynamo Engine Error: {str(e)}"}

@app.post("/generate-radio")
async def radio(req: ChatReq):
    try:
        return await voice.generate_voice_stream(req.message)
    except Exception as e:
        return {"error": str(e)}

@app.post("/generate-word")
async def word_exp(req: dict): 
    return export.word(req.get('history', []))

@app.post("/generate-ppt")
async def ppt_exp(req: dict): 
    return export.ppt(req.get('history', []))

@app.post("/generate-report")
async def pdf_exp(req: dict): 
    return export.pdf(req.get('history', []))

@app.post("/analyze-data")
async def analyze_data(file: UploadFile = File(...)):
    # analysis.py
    contents = await file.read()
    return analysis.process_data(contents, file.filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
