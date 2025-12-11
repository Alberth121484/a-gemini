import httpx
import structlog
from typing import Optional

import google.generativeai as genai

from ..config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class ImageGenerationTool:
    """Image generation using Google Imagen."""
    
    name = "image_generation"
    description = "Generates images from text prompts. Use when user asks to create or generate an image."
    
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model_name = f"models/{settings.image_model}"
    
    async def execute(self, prompt: str) -> tuple[bytes, str]:
        """Generate an image from a text prompt.
        
        Returns:
            tuple: (image_bytes, mime_type)
        """
        try:
            # Use Imagen model for image generation
            imagen = genai.ImageGenerationModel(self.model_name)
            
            response = await imagen.generate_images_async(
                prompt=prompt,
                number_of_images=1,
            )
            
            if response.images:
                image = response.images[0]
                return image._pil_image.tobytes(), "image/png"
            
            raise ValueError("No image generated")
            
        except Exception as e:
            logger.error("Image generation error", error=str(e), prompt=prompt[:100])
            raise


class ImageGenerationToolAlternative:
    """Alternative image generation using REST API directly."""
    
    name = "image_generation"
    description = "Generates images from text prompts."
    
    def __init__(self):
        self.api_key = settings.google_api_key
        self.model = settings.image_model
    
    async def execute(self, prompt: str) -> tuple[bytes, str]:
        """Generate image using REST API."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateImages"
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    params={"key": self.api_key},
                    json={
                        "prompt": prompt,
                        "number_of_images": 1,
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            if data.get("images"):
                import base64
                image_data = base64.b64decode(data["images"][0]["bytesBase64Encoded"])
                mime_type = data["images"][0].get("mimeType", "image/png")
                return image_data, mime_type
            
            raise ValueError("No image in response")
            
        except Exception as e:
            logger.error("Image generation error", error=str(e))
            raise
