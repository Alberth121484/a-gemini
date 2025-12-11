import httpx
import base64
import structlog
from typing import Optional

import google.generativeai as genai

from ..config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class ImageAnalysisTool:
    """Image analysis using Google Gemini Vision."""
    
    name = "image_analysis"
    description = "Analyzes images and describes their content. Use when user sends an image."
    
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-pro")
    
    async def download_image(self, url: str, slack_token: str) -> bytes:
        """Download image from Slack with authentication."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {slack_token}"},
                follow_redirects=True
            )
            response.raise_for_status()
            return response.content
    
    async def execute(
        self, 
        image_url: str, 
        prompt: str = "Analiza la imagen que te envían",
        slack_token: Optional[str] = None
    ) -> str:
        """Analyze an image and return description."""
        try:
            # Download image
            token = slack_token or settings.slack_bot_token
            image_data = await self.download_image(image_url, token)
            
            # Determine MIME type from URL
            mime_type = "image/jpeg"
            if ".png" in image_url.lower():
                mime_type = "image/png"
            elif ".gif" in image_url.lower():
                mime_type = "image/gif"
            elif ".webp" in image_url.lower():
                mime_type = "image/webp"
            
            # Create image part for Gemini
            image_part = {
                "mime_type": mime_type,
                "data": image_data
            }
            
            # Generate response
            response = await self.model.generate_content_async(
                [prompt, image_part],
                generation_config=genai.GenerationConfig(
                    max_output_tokens=2048,
                    temperature=0.7,
                )
            )
            
            return response.text
            
        except httpx.HTTPStatusError as e:
            logger.error("Image download error", status=e.response.status_code, url=image_url)
            return f"Error al descargar la imagen: {e.response.status_code}"
        except Exception as e:
            logger.error("Image analysis error", error=str(e))
            return f"Error al analizar la imagen: {str(e)}"
