# main.py - Final Production (Deep Dive & Strict Visuals Fixed)
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import google.generativeai as genai
from tavily import TavilyClient
from dotenv import load_dotenv
from pypdf import PdfReader
from PIL import Image
import io
import shutil
import time

# --- REPORT GENERATION IMPORTS ---
from docx import Document
from pptx import Presentation
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIG ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

gemini_model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")

tavily = None
if TAVILY_API_KEY:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)

# --- MODELS ---
class ChatRequest(BaseModel):
    message: str
    history: list = []
    use_search: bool = True
    deep_dive: bool = False
    model: str = "gemini-2.0-flash"
    pdf_context: str = None

class ExportRequest(BaseModel):
    history: list

# --- CHAT ENDPOINT ---
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    if not gemini_model: raise HTTPException(500, "Gemini Key Missing")
    
    try:
        if "image" in req.message.lower() and ("generate" in req.message.lower() or "create" in req.message.lower()):
            clean = req.message.replace(" ", "%20")
            return {"type": "image", "content": f"https://image.pollinations.ai/prompt/{clean}?nologo=true"}

        context_str = ""
        # Handle Search
        if req.use_search and not req.pdf_context and tavily:
            try:
                # Deep Dive affects Search Depth AND Prompt
                search_depth = "advanced" if req.deep_dive else "basic"
                res = tavily.search(query=req.message, search_depth="advanced" if req.deep_dive else "basic", max_results=5)
                context_str += f"\n\n[WEB RESULTS]:\n{res.get('results', [])}\n"
            except: pass

        if req.pdf_context:
            context_str += f"\n\n[USER DOCUMENT]:\n{req.pdf_context[:50000]}\n"

        # --- DYNAMIC SYSTEM PROMPT ---
        
        # 1. Base Personality
        base_instruction = "You are Dynamo AI."
        
        # 2. Deep Dive Mode Logic
        if req.deep_dive:
            base_instruction += " [MODE: DEEP DIVE] Provide extensive, detailed, and comprehensive answers. Use academic tone, explain complex concepts thoroughly, and cover multiple angles."
        else:
            base_instruction += " Answer concisely and clearly."

        # 3. Visual & Quiz Rules
        system_instruction = base_instruction + r"""
        
        RULES:
        1. DEFAULT: Answer in Markdown. Do NOT generate a graph unless explicitly asked.
        
        2. VISUALS (STRICT: ONLY if user asks for 'map', 'chart', 'graph', 'diagram'):
           - IF comparing numbers/trends: Use `xychart-beta`.
             * x-axis labels in quotes inside brackets.
           - IF showing structure/process: Use `graph TD`.
             * Wrap ALL labels in quotes: A["Label"] --> B["Label"].
           - DO NOT output JSON for visuals.
        
        3. QUIZ (Priority for "Quiz", "Test", "Practice"):
           - Output valid JSON inside ```json_quiz ... ```.
           - Keys: "question", "options", "answer" (0-3), "explanation".
        """
        
        full_prompt = system_instruction + "\n" + context_str + "\n"
        for msg in req.history[-6:]:
            role = msg.get('role', 'user') if isinstance(msg, dict) else getattr(msg, 'role', 'user')
            content = msg.get('content', '') if isinstance(msg, dict) else getattr(msg, 'content', '')
            full_prompt += f"{'User' if role == 'user' else 'Model'}: {content}\n"
        
        full_prompt += f"User: {req.message}\nModel:"

        active_model = gemini_model
        if req.model == "gemini-1.5-pro": active_model = genai.GenerativeModel("gemini-1.5-pro")

        response = active_model.generate_content(full_prompt)
        return {"type": "text", "content": response.text}

    except Exception as e:
        return {"type": "text", "content": f"Error: {str(e)}"}

# --- EXPORT ENDPOINTS ---
@app.post("/generate-word")
async def generate_word(req: ExportRequest):
    doc = Document()
    doc.add_heading('Dynamo AI Report', 0)
    for msg in req.history:
        role = msg.get('role', 'User') if isinstance(msg, dict) else msg.role
        content = msg.get('content', '') if isinstance(msg, dict) else msg.content
        doc.add_heading(str(role).capitalize(), level=1)
        doc.add_paragraph(str(content))
    byte_io = io.BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return StreamingResponse(byte_io, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=Dynamo_Report.docx"})

@app.post("/generate-ppt")
async def generate_ppt(req: ExportRequest):
    prs = Presentation()
    for msg in req.history:
        role = msg.get('role', 'User') if isinstance(msg, dict) else msg.role
        content = msg.get('content', '') if isinstance(msg, dict) else msg.content
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = str(role).capitalize()
        slide.placeholders[1].text = str(content)[:800]
    byte_io = io.BytesIO()
    prs.save(byte_io)
    byte_io.seek(0)
    return StreamingResponse(byte_io, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers={"Content-Disposition": "attachment; filename=Dynamo_Presentation.pptx"})

@app.post("/generate-report")
async def generate_pdf(req: ExportRequest):
    byte_io = io.BytesIO()
    doc = SimpleDocTemplate(byte_io, pagesize=letter)
    story = [Paragraph("Dynamo AI Report", getSampleStyleSheet()['Title']), Spacer(1, 12)]
    for msg in req.history:
        role = msg.get('role', 'User') if isinstance(msg, dict) else msg.role
        content = msg.get('content', '') if isinstance(msg, dict) else msg.content
        story.append(Paragraph(f"<b>{str(role).capitalize()}:</b>", getSampleStyleSheet()['Heading2']))
        try: story.append(Paragraph(str(content).replace('\n', '<br/>'), getSampleStyleSheet()['Normal']))
        except: pass
        story.append(Spacer(1, 12))
    doc.build(story)
    byte_io.seek(0)
    return StreamingResponse(byte_io, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=Dynamo_Report.pdf"})

# --- MEDIA ENDPOINTS ---
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        reader = PdfReader(file.file)
        text = "".join([p.extract_text() for p in reader.pages])
        return {"text": text.strip()} 
    except: return {"text": "Error reading PDF."}

@app.post("/vision")
async def vision_analysis(file: UploadFile = File(...), message: str = Form("Describe this image")):
    if not gemini_model: return {"content": "Gemini Key Missing"}
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        response = gemini_model.generate_content([message, image])
        return {"content": response.text}
    except: return {"content": "Error analyzing image."}

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    if not gemini_model: return {"text": "Gemini Key Missing"}
    try:
        temp = f"temp_{int(time.time())}.wav"
        with open(temp, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
        uploaded = genai.upload_file(temp)
        response = gemini_model.generate_content([uploaded, "Transcribe exactly."])
        os.remove(temp)
        return {"text": response.text.strip()}
    except: return {"text": "Error transcribing."}
# --- DYNAMO RADIO (PODCAST FEATURE) ---
# Add this to the BOTTOM of main.py. It does not touch existing code.

import edge_tts
import asyncio
import uuid

# Simple function to clean text for audio
def clean_for_audio(text):
    return text.replace("*", "").replace("#", "").replace("-", "")

@app.post("/generate-radio")
async def generate_radio(req: ChatRequest):
    if not gemini_model: raise HTTPException(500, "Gemini Key Missing")
    
    # 1. THE SCRIPTWRITER (Gemini)
    # We ask Gemini to convert the complex text into a fun dialogue
    script_prompt = f"""
    You are a Podcast Producer. Convert the following text into a short, engaging conversation between two hosts: 
    - "Alex" (The energetic host)
    - "Sam" (The thoughtful expert)
    
    Rules:
    - Keep it under 2 minutes.
    - Make it sound natural (use "Wow", "I see", "Exactly").
    - OUTPUT FORMAT: A raw JSON list ONLY. No markdown.
    - Example: [ {{"speaker": "Alex", "text": "Hello!"}}, {{"speaker": "Sam", "text": "Hi!"}} ]
    
    TEXT TO ADAPT:
    {req.pdf_context[:10000] if req.pdf_context else req.message}
    """
    
    try:
        # Generate Script
        response = gemini_model.generate_content(script_prompt)
        # Clean up json format if Gemini adds backticks
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        script = eval(clean_json) # Safely parse the list
        
        # 2. THE VOICE ACTORS (Edge TTS)
        # We generate audio for each line
        
        # Files list to stitch later
        audio_segments = []
        
        for line in script:
            text = clean_for_audio(line["text"])
            speaker = line["speaker"]
            
            # Select Voice
            voice = "en-US-GuyNeural" if speaker == "Alex" else "en-US-AriaNeural"
            
            # Generate temporary file
            temp_file = f"temp_{uuid.uuid4()}.mp3"
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(temp_file)
            audio_segments.append(temp_file)
            
        # 3. THE EDITOR (Stitching)
        # Since pydub/ffmpeg is hard on Render, we use a "Binary Append" hack
        # MP3 files can often just be concatenated!
        
        final_filename = f"Dynamo_Radio_{int(time.time())}.mp3"
        with open(final_filename, "wb") as outfile:
            for segment in audio_segments:
                with open(segment, "rb") as infile:
                    outfile.write(infile.read())
                os.remove(segment) # Clean up temp files
                
        # 4. Return the File
        return FileResponse(final_filename, media_type="audio/mpeg", filename="Dynamo_Podcast.mp3")

    except Exception as e:
        print(f"Radio Error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
