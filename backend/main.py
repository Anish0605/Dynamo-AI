from fastapi import FastAPI, Request
from supabase_client import supabase
from datetime import datetime
import uuid

app = FastAPI()

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()

    user_id = body.get("user_id")        # supabase user id
    chat_id = body.get("chat_id")        # optional
    message = body.get("message")

    if not user_id or not message:
        return {"error": "Missing user_id or message"}

    # 1️⃣ Create chat if not exists
    if not chat_id:
        chat_id = str(uuid.uuid4())
        supabase.table("chats").insert({
            "id": chat_id,
            "user_id": user_id,
            "title": message[:40],
            "created_at": datetime.utcnow().isoformat()
        }).execute()

    # 2️⃣ Save user message
    supabase.table("messages").insert({
        "chat_id": chat_id,
        "role": "user",
        "content": message
    }).execute()

    # 3️⃣ AI RESPONSE (replace with Gemini/Groq call)
    ai_reply = f"I received your message: {message}"

    # 4️⃣ Save assistant message
    supabase.table("messages").insert({
        "chat_id": chat_id,
        "role": "assistant",
        "content": ai_reply
    }).execute()

    return {
        "chat_id": chat_id,
        "reply": ai_reply
    }
