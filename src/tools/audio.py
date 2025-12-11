import httpx
import io
import structlog
from typing import Optional

from openai import AsyncOpenAI

from ..config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class AudioTranscriber:
    """Audio transcription using OpenAI Whisper."""
    
    name = "audio_transcriber"
    description = "Transcribes audio files to text."
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.slack_token = settings.slack_bot_token
    
    async def download_audio(self, url: str) -> bytes:
        """Download audio file from Slack."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {self.slack_token}"},
                follow_redirects=True
            )
            response.raise_for_status()
            return response.content
    
    async def execute(self, audio_url: str) -> str:
        """Transcribe audio to text."""
        try:
            # Download audio
            audio_data = await self.download_audio(audio_url)
            
            # Create file-like object
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.mp4"  # Whisper needs a filename
            
            # Transcribe
            transcription = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
            
            return transcription.text
            
        except Exception as e:
            logger.error("Audio transcription error", error=str(e))
            return f"Error al transcribir el audio: {str(e)}"


class AudioGenerator:
    """Audio generation using OpenAI TTS."""
    
    name = "audio_generator"
    description = "Generates audio from text."
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    async def execute(self, text: str, voice: str = "onyx") -> bytes:
        """Generate audio from text.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        
        Returns:
            Audio bytes (MP3)
        """
        try:
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
            )
            
            return response.content
            
        except Exception as e:
            logger.error("Audio generation error", error=str(e))
            raise
