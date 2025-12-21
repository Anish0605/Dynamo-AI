# model.py
import google.generativeai as genai
from groq import Groq
import config

# Initialize AI Clients safely
try:
    if config.GEMINI_KEY:
        genai.configure(api_key=config.GEMINI_KEY)
    
    groq_client = None
    if config.GROQ_KEY:
        groq_client = Groq(api_key=config.GROQ_KEY)
except Exception as e:
    print("AI Client Initialization Error: " + str(e))

def get_ai_response(prompt, history, model_name, context=""):
    """
    Core AI Routing. No longer depends on flowchart.py.
    """
    msg_lower = prompt.lower()
    
    # 1. Identity Guard
    if any(q in msg_lower for q in ["who are you", "your name", "what is your name", "who made you"]):
        return config.DYNAMO_IDENTITY

    # 2. Direct System Instruction (Simplified to avoid SyntaxErrors)
    sys_instr = "You are Dynamo AI. " + config.DYNAMO_IDENTITY + " "
    sys_instr += "Provide professional research data and respond in clear Markdown."

    # 3. Construct Prompt
    full_prompt = sys_instr + "\n\nCONTEXT FROM RESEARCH:\n" + context + "\n\nUSER QUERY: " + prompt + "\nAI:"

    # 4. Routing Logic
    if "llama3" in model_name and groq_client:
        messages = [{"role": "system", "content": sys_instr}]
        if context:
            messages.append({"role": "system", "content": "Context: " + context})
        
        # Add conversation history
        for m in history[-5:]:
            messages.append({"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            completion = groq_client.chat.completions.create(messages=messages, model=model_name)
            return completion.choices[0].message.content
        except Exception as e:
            return "Groq Error: " + str(e)
    else:
        # Default to Gemini 2.0 Flash
        try:
            gen_model = genai.GenerativeModel("gemini-2.0-flash")
            response = gen_model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return "Gemini Error: " + str(e)
