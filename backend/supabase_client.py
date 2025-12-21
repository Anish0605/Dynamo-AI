#supabase_client.py
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def get_user_profile(firebase_uid: str):
    """Fetch user profile from Supabase."""
    if not supabase: return None
    res = supabase.table("users").select("*").eq("firebase_uid", firebase_uid).execute()
    return res.data[0] if res.data else None

def save_chat_log(user_id: str, title: str):
    """backend side chat creation if needed."""
    if not supabase: return None
    res = supabase.table("chats").insert({"user_id": user_id, "title": title}).execute()
    return res.data[0] if res.data else None
