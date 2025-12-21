#image.py
import aiohttp
import base64
import uuid

async def generate_image_base64(prompt):
    """
    Fetches an image from the source, converts it to base64, 
    and returns a payload that allows for frontend downloading.
    """
    clean_prompt = prompt.replace(" ", "%20")
    # We fetch the actual image data so we can encode it for the "Download Image" button
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?nologo=true&width=1024&height=1024&seed={uuid.uuid4()}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    b64_string = base64.b64encode(image_data).decode('utf-8')
                    return {
                        "type": "image_v2", 
                        "content": f"data:image/jpeg;base64,{b64_string}", 
                        "prompt": prompt
                    }
                else:
                    return {"type": "text", "content": "Dynamo was unable to generate that image right now."}
        except Exception as e:
            return {"type": "text", "content": f"Vision Engine Error: {str(e)}"}
