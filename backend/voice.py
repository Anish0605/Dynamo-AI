# voice.py
import uuid
import os
import edge_tts
from fastapi.responses import FileResponse

async def generate_voice_stream(text):
    """
    Generates an MP3 file from text and returns it as a FileResponse.
    """
    # Create a unique filename for the temporary audio
    temp_filename = "voice_" + str(uuid.uuid4()) + ".mp3"
    
    # We use en-IN-PrabhatNeural for a clear professional voice
    communicate = edge_tts.Communicate(text, "en-IN-PrabhatNeural")
    
    try:
        await communicate.save(temp_filename)
        # Returns the file and Render will serve it to the frontend
        return FileResponse(temp_filename, media_type="audio/mpeg")
    except Exception as e:
        print("Voice Error: " + str(e))
        return None
