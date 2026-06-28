# ===== HELPER FUNCTIONS =====
async def generate_image_with_gemini(prompt: str):
    """Generate image using Google Gemini API"""
    if not GEMINI_API_KEY:
        return None, "Gemini API key not configured."
    
    # Use the correct model name for the Gemini API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"]  # This is required for image generation!
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract image from response
                    if "candidates" in data and data["candidates"]:
                        candidate = data["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            for part in candidate["content"]["parts"]:
                                if "inlineData" in part:
                                    # Image data is base64 encoded
                                    image_data = part["inlineData"]["data"]
                                    return image_data, "Image generated successfully!"
                                
                                elif "text" in part:
                                    # The model might return text along with the image
                                    continue
                    
                    return None, "No image data found in response"
                else:
                    error_text = await response.text()
                    return None, f"API Error: {response.status} - {error_text}"
    except Exception as e:
        logger.error(f"Gemini API Error: {str(e)}")
        return None, f"Error: {str(e)}"
