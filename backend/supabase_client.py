#supabase_client.py
from supabase import create_client
import config

# Initialize safely using service role key from config
supabase = None
if config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
    try:
        supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    except Exception as e:
        print(f"Supabase Connection Error: {e}")

def fetch_user(firebase_uid: str):
    if not supabase: return None
    try:
        res = supabase.table("users").select("*").eq("firebase_uid", firebase_uid).execute()
        return res.data[0] if res.data else None
    except:
        return None

def save_chat_log(user_id: str, title: str):
    """backend side chat creation if needed."""
    if not supabase: return None
    try:
        res = supabase.table("chats").insert({"user_id": user_id, "title": title}).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Database Insert Error: {e}")
        return None