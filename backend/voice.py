#voice.py
import uuid, os, edge_tts
from fastapi.responses import FileResponse

async def generate_voice_stream(text):
    temp_filename = f"voice_{uuid.uuid4()}.mp3"
    communicate = edge_tts.Communicate(text, "en-IN-PrabhatNeural")
    await communicate.save(temp_filename)
    return FileResponse(temp_filename, media_type="audio/mpeg")