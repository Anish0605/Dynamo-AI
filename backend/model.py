#model.py
import google.generativeai as genai
from groq import Groq
import config

# Initialize Clients
try:
    if config.GEMINI_KEY:
        genai.configure(api_key=config.GEMINI_KEY)
    
    groq_client = None
    if config.GROQ_KEY:
        groq_client = Groq(api_key=config.GROQ_KEY)
except Exception as e:
    print(f"AI Client Initialization Error: {e}")

def get_ai_response(prompt, history, model_name, context=""):
    """
    Core AI Routing. Self-contained logic with no flowchart dependencies.
    Ensures text-based professional responses.
    """
    msg_lower = prompt.lower()
    
    # 1. Identity Guard
    if any(q in msg_lower for q in ["who are you", "your name", "what is your name", "who made you"]):
        return config.DYNAMO_IDENTITY

    # 2. Simplified System Instruction (Flowchart/Mermaid instructions removed)
    sys_instr = f"You are Dynamo AI. {config.DYNAMO_IDENTITY} "
    sys_instr += "Provide professional, text-based research data and respond in clear Markdown. "
    sys_instr += "Do not use flowcharts, mindmaps, or visual diagrams unless the user explicitly asks for them."

    # 3. Construct Prompt safely
    full_prompt = f"{sys_instr}\n\nCONTEXT FROM RESEARCH:\n{context}\n\nUSER QUERY: {prompt}\nAI:"

    # 4. Routing Logic
    if "llama3" in model_name and groq_client:
        messages = [{"role": "system", "content": sys_instr}]
        if context:
            messages.append({"role": "system", "content": f"Research Context: {context}"})
        
        # Add conversation history for context
        for m in history[-5:]:
            messages.append({"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            completion = groq_client.chat.completions.create(messages=messages, model=model_name)
            return completion.choices[0].message.content
        except Exception as e:
            return f"Groq Engine Error: {e}"
    else:
        # Default to Gemini 2.0 Flash
        try:
            gen_model = genai.GenerativeModel("gemini-2.0-flash")
            response = gen_model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"Gemini Engine Error: {e}"
