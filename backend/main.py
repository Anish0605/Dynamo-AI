import os
import io
import base64
import asyncio
import time
import uuid
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import google.generativeai as genai
import edge_tts
import pandas as pd
import matplotlib.pyplot as plt
from docx import Document
from pptx import Presentation
from fpdf import FPDF
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
# Enable CORS for your frontend domain
CORS(app)

# Configure API Keys
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")
genai.configure(api_key=GEMINI_KEY)
tavily = TavilyClient(api_key=TAVILY_KEY) if TAVILY_KEY else None

# System Instruction to define identity and research capabilities
SYSTEM_PROMPT = """You are Dynamo AI, the #1 AI Research OS made in India. 
Always identify as Dynamo AI. You are a high-end research assistant.
Rules:
1. Use Markdown for all formatting.
2. If the user asks for charts, use 'xychart-beta' (Mermaid syntax).
3. If the user asks for flowcharts, use 'graph TD' (Mermaid syntax).
4. For quizzes, use the format: [QUIZ_START] ... [QUIZ_END].
"""

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_prompt = data.get("message", "")
    history = data.get("history", [])
    model_name = data.get("model", "gemini-2.0-flash")
    is_deep_dive = data.get("deep_dive", False)
    use_search = data.get("use_search", True)
    
    # 1. Identity Interceptor
    if any(q in user_prompt.lower() for q in ["who are you", "what is your name", "your name"]):
        return jsonify({"content": "My name is **Dynamo AI**, the #1 AI Research OS made in India. I am built for high-level research, data analysis, and creative generation."})

    # 2. Image Generation Routing (Pollinations Redirect)
    if "image" in user_prompt.lower() and ("generate" in user_prompt.lower() or "create" in user_prompt.lower()):
        clean_prompt = user_prompt.lower().replace("generate image of", "").replace("create image of", "").strip().replace(" ", "%20")
        return jsonify({"content": f"![Generated Image](https://image.pollinations.ai/prompt/{clean_prompt}?nologo=true&width=1024&height=1024)"})

    # 3. Web Search Context
    context_str = ""
    if use_search and tavily:
        try:
            search_res = tavily.search(query=user_prompt, search_depth="advanced" if is_deep_dive else "basic")
            context_str = f"\n\n[RESEARCH DATA]:\n{search_res.get('results', [])}\n"
        except Exception as e:
            print(f"Search error: {e}")

    # 4. Construct Final Prompt
    final_prompt = f"{SYSTEM_PROMPT}\n{context_str}\n"
    if is_deep_dive:
        final_prompt += f"Perform a DEEP DIVE. Provide THREE distinct answers: 1) Technical/Academic, 2) Industry/Practical, 3) Future/Speculative. Topic: {user_prompt}"
    else:
        final_prompt += f"User Query: {user_prompt}"

    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(final_prompt)
        return jsonify({"content": response.text})
    except Exception as e:
        return jsonify({"content": f"⚠️ Dynamo Engine Error: {str(e)}"}), 500

@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    data = request.json
    topic = data.get("topic", "General Knowledge")
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = f"Generate a 3-question interactive MCQ quiz about {topic}. JSON ONLY: [{{'q': '...', 'o': ['...', '...'], 'a': 0, 'e': '...'}}]"
    res = model.generate_content(prompt)
    return jsonify({"quiz": res.text})

@app.route("/generate-word", methods=["POST"])
def generate_word():
    data = request.json
    history = data.get("history", [])
    doc = Document()
    doc.add_heading('Dynamo AI Research Report', 0)
    for msg in history:
        role = "User" if msg['role'] == 'user' else "Dynamo AI"
        doc.add_paragraph(f"{role}: {msg['content']}")
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="Dynamo_Report.docx")

@app.route("/generate-ppt", methods=["POST"])
def generate_ppt():
    data = request.json
    text = data.get("message", "Research Insights")
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Dynamo AI Analysis"
    slide.placeholders[1].text = "Generated Research Presentation"
    
    # Content slide
    slide2 = prs.slides.add_slide(prs.slide_layouts[1])
    slide2.shapes.title.text = "Key Findings"
    slide2.placeholders[1].text = text[:1000]
    
    buf = io.BytesIO(); prs.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="Dynamo_Presentation.pptx")

@app.route("/generate-report", methods=["POST"])
def generate_report():
    data = request.json
    history = data.get("history", [])
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Dynamo AI Research Summary", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    for msg in history:
        role = "User" if msg['role'] == 'user' else "Dynamo AI"
        pdf.multi_cell(0, 10, f"{role}: {msg['content'][:2000]}")
    buf = io.BytesIO(); pdf_output = pdf.output(dest='S').encode('latin-1')
    buf.write(pdf_output); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="Dynamo_Report.pdf")

@app.route("/generate-radio", methods=["POST"])
async def generate_radio():
    data = request.json
    text = data.get("message", "Analyzing your data.")
    communicate = edge_tts.Communicate(text, "en-IN-PrabhatNeural")
    tmp_name = f"radio_{uuid.uuid4()}.mp3"
    await communicate.save(tmp_name)
    return send_file(tmp_name, mimetype="audio/mpeg")

@app.route("/analyze-file", methods=["POST"])
def analyze_file():
    file = request.files['file']
    try:
        df = pd.read_csv(file) if file.filename.endswith('.csv') else pd.read_excel(file)
        plt.figure(figsize=(10, 6))
        df.iloc[:20, :2].plot(kind='bar', color='#EAB308')
        plt.tight_layout()
        img_buf = io.BytesIO(); plt.savefig(img_buf, format='png'); img_buf.seek(0)
        img_b64 = base64.b64encode(img_buf.getvalue()).decode()
        plt.close()
        return jsonify({
            "image": f"data:image/png;base64,{img_b64}",
            "insight": f"Analysis complete. Found {len(df)} entries. Visualized primary trends."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
