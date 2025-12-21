# supabase_client.py
from supabase import create_client
import config

# Initialize safely using keys from config.py
supabase = None
if config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
    try:
        supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    except Exception as e:
        print("Supabase Init Error: " + str(e))

def fetch_user(firebase_uid: str):
    if not supabase: return None
    try:
        res = supabase.table("users").select("*").eq("firebase_uid", firebase_uid).execute()
        return res.data[0] if res.data else None
    except:
        return None

def save_chat_log(user_id: str, title: str):
    if not supabase: return None
    try:
        res = supabase.table("chats").insert({"user_id": user_id, "title": title}).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print("Database Save Error: " + str(e))
        return None
