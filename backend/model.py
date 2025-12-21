#model.py
import google.generativeai as genai
from groq import Groq
import config
import flowchart

# Initialize Clients
genai.configure(api_key=config.GEMINI_KEY)
groq_client = Groq(api_key=config.GROQ_KEY) if config.GROQ_KEY else None

def get_ai_response(prompt, history, model_name, context=""):
    """
    Core AI Routing logic. 
    Matches the 'model' name requested by main.py.
    """
    msg_lower = prompt.lower()
    # 1. Identity Guard
    if any(q in msg_lower for q in ["who are you", "your name", "what is your name"]):
        return config.DYNAMO_IDENTITY

    # 2. Inject Formatting Rules
    sys_instr = flowchart.get_system_instruction()
    full_prompt = f"{sys_instr}\n\nCONTEXT FROM RESEARCH:\n{context}\n\nUSER QUERY: {prompt}\nDYNAMO AI:"

    # 3. Execution
    if "llama3" in model_name and groq_client:
        messages = [{"role": "system", "content": sys_instr}]
        if context: messages.append({"role": "system", "content": f"Context: {context}"})
        for m in history[-5:]:
            messages.append({"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']})
        messages.append({"role": "user", "content": prompt})
        
        completion = groq_client.chat.completions.create(messages=messages, model=model_name)
        return completion.choices[0].message.content
    else:
        # Default Gemini 2.0 Flash
        gen_model = genai.GenerativeModel("gemini-2.0-flash")
        response = gen_model.generate_content(full_prompt)
        return response.text
