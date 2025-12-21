#image.py
import aiohttp
import base64
import uuid
import config

async def generate_image_base64(prompt):
    """
    Generates images and converts to Base64 to enable the 
    'Download Image' button in the frontend.
    """
    clean_prompt = prompt.replace(" ", "%20")
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?nologo=true&width=1024&height=1024"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    b64 = base64.b64encode(data).decode('utf-8')
                    return {
                        "type": "image_v2", 
                        "content": f"data:image/jpeg;base64,{b64}", 
                        "prompt": prompt
                    }
        except:
            pass
    return {"type": "text", "content": "Visual system busy. Please try again."}