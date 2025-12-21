#config.py
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
TAVILY_KEY = os.getenv("TAVILY_API_KEY")

# Supabase Config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Identity Branding
DYNAMO_IDENTITY = "My name is **Dynamo AI**, the #1 AI Research OS made in India. I specialize in deep-data intelligence, visual systems, and professional research."