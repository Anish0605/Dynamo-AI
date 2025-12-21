# image.py
import aiohttp
import base64
import uuid

async def generate_image_base64(prompt):
    """
    Generates images and converts to Base64 for the frontend.
    """
    clean_prompt = prompt.replace(" ", "%20")
    # Using Pollinations for instant visual generation
    url = "https://image.pollinations.ai/prompt/" + clean_prompt + "?nologo=true&width=1024&height=1024&seed=" + str(uuid.uuid4())
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    b64 = base64.b64encode(data).decode('utf-8')
                    return {
                        "type": "image_v2", 
                        "content": "data:image/jpeg;base64," + b64, 
                        "prompt": prompt
                    }
        except Exception as e:
            print("Image Gen Error: " + str(e))
    
    return {"type": "text", "content": "Visual system is currently busy."}
