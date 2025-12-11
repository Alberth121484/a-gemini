import io
import asyncio
from datetime import datetime
import structlog
from typing import Optional

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient

from .config import get_settings
from .agent import get_agent
from .database import RateLimiter, init_db_pool, init_redis

logger = structlog.get_logger()
settings = get_settings()

# Initialize Slack app
app = AsyncApp(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)

rate_limiter = RateLimiter()


def get_file_info(event: dict) -> tuple[Optional[str], Optional[str]]:
    """Extract file URL and type from Slack event."""
    files = event.get("files", [])
    if not files:
        return None, None
    
    file_info = files[0]
    url = file_info.get("url_private_download") or file_info.get("url_private")
    mime_type = file_info.get("mimetype", "")
    
    return url, mime_type


def is_audio_message(event: dict) -> bool:
    """Check if the message contains audio."""
    files = event.get("files", [])
    if files:
        mime_type = files[0].get("mimetype", "")
        return mime_type.startswith("audio/")
    return False


def is_image_message(event: dict) -> bool:
    """Check if the message contains an image."""
    files = event.get("files", [])
    if files:
        mime_type = files[0].get("mimetype", "")
        return mime_type.startswith("image/")
    return False


def is_document_message(event: dict) -> bool:
    """Check if the message contains a document."""
    files = event.get("files", [])
    if files:
        mime_type = files[0].get("mimetype", "")
        return not mime_type.startswith("audio/") and not mime_type.startswith("image/") and not mime_type.startswith("video/")
    return False


@app.event("message")
async def handle_message(event: dict, client: AsyncWebClient, say):
    """Handle incoming Slack messages."""
    # Ignore bot messages and message edits
    if event.get("bot_id") or event.get("subtype") in ["message_changed", "message_deleted"]:
        return
    
    user_id = event.get("user")
    channel_id = event.get("channel")
    message_text = event.get("text", "")
    message_ts = event.get("ts")
    
    if not user_id or not channel_id:
        return
    
    logger.info("Received message", user=user_id, channel=channel_id, has_files=bool(event.get("files")))
    
    try:
        # Rate limiting check
        allowed, remaining = await rate_limiter.is_allowed(user_id)
        if not allowed:
            await client.chat_postMessage(channel=channel_id, text="⚠️ Has alcanzado el límite de solicitudes. Por favor espera un momento.")
            return
        
        # Add "eyes" reaction to show processing
        try:
            await client.reactions_add(
                channel=channel_id,
                timestamp=message_ts,
                name="eyes"
            )
        except Exception:
            pass  # Ignore reaction errors
        
        # Get user info for logging
        try:
            user_info = await client.users_info(user=user_id)
            username = user_info["user"]["profile"].get("display_name") or user_info["user"]["name"]
            email = f"{user_info['user']['name']}@tiendasneto.com"
        except Exception:
            username = user_id
            email = f"{user_id}@unknown.com"
        
        # Get agent
        agent = get_agent()
        
        # Get file info
        file_url, file_type = get_file_info(event)
        
        # Process based on message type
        if is_audio_message(event):
            # Audio message - transcribe and respond with audio
            result = await agent.process_audio_message(
                user_id=user_id,
                audio_url=file_url,
                username=username,
                email=email,
            )
            
            # Send audio response
            if result.get("audio_bytes"):
                await client.files_upload_v2(
                    channel=channel_id,
                    content=result["audio_bytes"],
                    filename=f"audio-{datetime.now().strftime('%Y-%m-%d')}.mp3",
                )
            elif result.get("text"):
                await client.chat_postMessage(channel=channel_id, text=result["text"])
        
        else:
            # Text, image, or document message
            result = await agent.process_message(
                user_id=user_id,
                message=message_text,
                file_url=file_url,
                file_type=file_type,
                username=username,
                email=email,
            )
            
            # Send image if generated
            if result.get("image_bytes"):
                await client.files_upload_v2(
                    channel=channel_id,
                    content=result["image_bytes"],
                    filename=f"img-{datetime.now().strftime('%Y-%m-%d_%H-%M')}.png",
                    title=result.get("text", "Imagen generada"),
                )
            
            # Send text response
            if result.get("text") and not result.get("image_bytes"):
                # Split long messages
                text = result["text"]
                if len(text) > 3900:
                    chunks = [text[i:i+3900] for i in range(0, len(text), 3900)]
                    for chunk in chunks:
                        await client.chat_postMessage(channel=channel_id, text=chunk)
                else:
                    await client.chat_postMessage(channel=channel_id, text=text)
        
        # Remove "eyes" and add checkmark
        try:
            await client.reactions_remove(
                channel=channel_id,
                timestamp=message_ts,
                name="eyes"
            )
            await client.reactions_add(
                channel=channel_id,
                timestamp=message_ts,
                name="white_check_mark"
            )
        except Exception:
            pass
        
    except Exception as e:
        logger.error("Message handling error", error=str(e), user=user_id)
        
        # Try to remove eyes reaction
        try:
            await client.reactions_remove(
                channel=channel_id,
                timestamp=message_ts,
                name="eyes"
            )
        except Exception:
            pass
        
        await client.chat_postMessage(channel=channel_id, text=f"Lo siento, ocurrió un error: {str(e)[:200]}")


@app.event("app_mention")
async def handle_mention(event: dict, client: AsyncWebClient, say):
    """Handle @mentions of the bot."""
    # Reuse message handler
    await handle_message(event, client, say)


async def start_slack_bot():
    """Start the Slack bot using Socket Mode."""
    # Initialize database and redis
    await init_db_pool()
    await init_redis()
    
    handler = AsyncSocketModeHandler(app, settings.slack_app_token)
    logger.info("Starting Slack bot...")
    await handler.start_async()


def run_slack_bot():
    """Run the Slack bot (blocking)."""
    asyncio.run(start_slack_bot())
