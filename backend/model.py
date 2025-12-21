# model.py
import google.generativeai as genai
from groq import Groq
import config
# REMOVED: import flowchart (This was causing the crash)

try:
    if config.GEMINI_KEY:
        genai.configure(api_key=config.GEMINI_KEY)
    groq_client = Groq(api_key=config.GROQ_KEY) if config.GROQ_KEY else None
except Exception as e:
    print("AI Init Error: " + str(e))

def get_instructions():
    # Integrated identity and visual rules directly into the brain
    instr = "You are Dynamo AI. " + str(config.DYNAMO_IDENTITY) + "\n"
    instr += "[VISUAL RULES]: Use mermaid graph TD for flowcharts. "
    instr += "Ensure labels are in double quotes like A[\"Text\"]."
    return instr

def get_ai_response(prompt, history, model_name, context=""):
    msg_lower = prompt.lower()
    if any(q in msg_lower for q in ["who are you", "your name"]):
        return config.DYNAMO_IDENTITY

    sys_instr = get_instructions()
    full_prompt = sys_instr + "\n\nCONTEXT: " + str(context) + "\n\nUSER: " + str(prompt) + "\nAI:"

    if "llama3" in model_name and groq_client:
        messages = [{"role": "system", "content": sys_instr}]
        for m in history[-5:]:
            messages.append({"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']})
        messages.append({"role": "user", "content": prompt})
        try:
            res = groq_client.chat.completions.create(messages=messages, model=model_name)
            return res.choices[0].message.content
        except Exception as e:
            return "Groq Error: " + str(e)
    else:
        try:
            m = genai.GenerativeModel("gemini-2.0-flash")
            res = m.generate_content(full_prompt)
            return res.text
        except Exception as e:
            return "Gemini Error: " + str(e)
