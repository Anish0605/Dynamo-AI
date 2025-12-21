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
    Core logic to route requests to either Gemini or Groq/LLaMA.
    Includes Dynamo AI Identity check and Mermaid instruction injection.
    """
    # 1. High-Priority Identity Check
    msg_lower = prompt.lower()
    if any(q in msg_lower for q in ["who are you", "your name", "what is your name", "who made you"]):
        return config.DYNAMO_IDENTITY

    # 2. Prepare Prompt with Mermaid Instructions
    sys_instr = flowchart.get_system_instruction()
    full_prompt = f"{sys_instr}\nCONTEXT:\n{context}\n\nUSER: {prompt}\nAI:"

    # 3. Routing
    if "llama3" in model_name and groq_client:
        messages = [{"role": "system", "content": sys_instr}]
        if context:
            messages.append({"role": "system", "content": f"Context: {context}"})
        # Add limited history for context
        for m in history[-6:]:
            messages.append({"role": "user" if m['role'] == 'user' else "assistant", "content": m['content']})
        messages.append({"role": "user", "content": prompt})
        
        completion = groq_client.chat.completions.create(messages=messages, model=model_name)
        return completion.choices[0].message.content
    else:
        # Default to Gemini 2.0 Flash
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(full_prompt)
        return response.text
