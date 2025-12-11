#!/usr/bin/env python3
"""
Main entry point for the optimized AI Agent.

Usage:
    # Run Slack bot (Socket Mode)
    python main.py slack
    
    # Run HTTP server (for webhooks/health checks)
    python main.py server
    
    # Run both
    python main.py all
"""

import sys
import asyncio
import signal
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import structlog

from src.config import get_settings
from src.database import init_db_pool, init_redis, close_db_pool, close_redis
from src.slack_handler import app as slack_app, start_slack_bot
from src.agent import get_agent

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Initializing application...")
    await init_db_pool()
    await init_redis()
    get_agent()  # Pre-initialize agent
    logger.info("Application initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await close_db_pool()
    await close_redis()
    logger.info("Application shut down successfully")


# FastAPI app for health checks and metrics
api = FastAPI(
    title="AI Agent API",
    version="1.0.0",
    lifespan=lifespan,
)


@api.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@api.get("/ready")
async def readiness_check():
    """Readiness check - verifies all dependencies are available."""
    from src.database import get_db_pool, get_redis
    
    try:
        # Check database
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        # Check Redis
        redis = await get_redis()
        await redis.ping()
        
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@api.get("/metrics")
async def metrics():
    """Basic metrics endpoint."""
    from src.database import get_db_pool, get_redis
    
    try:
        pool = await get_db_pool()
        redis = await get_redis()
        
        return {
            "database": {
                "pool_size": pool.get_size(),
                "pool_free": pool.get_idle_size(),
            },
            "redis": {
                "connected": await redis.ping(),
            }
        }
    except Exception as e:
        return {"error": str(e)}


async def run_server():
    """Run the HTTP server."""
    config = uvicorn.Config(
        api,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=True,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_all():
    """Run both Slack bot and HTTP server concurrently."""
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    
    # Initialize resources
    await init_db_pool()
    await init_redis()
    get_agent()
    
    # Create Slack handler
    handler = AsyncSocketModeHandler(slack_app, settings.slack_app_token)
    
    # Run both
    logger.info("Starting Slack bot and HTTP server...")
    
    async def run_slack():
        await handler.start_async()
    
    await asyncio.gather(
        run_slack(),
        run_server(),
    )


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    if mode == "slack":
        logger.info("Starting in Slack mode...")
        asyncio.run(start_slack_bot())
    
    elif mode == "server":
        logger.info("Starting in server mode...")
        uvicorn.run(
            "main:api",
            host=settings.host,
            port=settings.port,
            workers=settings.workers,
            log_level=settings.log_level.lower(),
        )
    
    elif mode == "all":
        logger.info("Starting in full mode (Slack + Server)...")
        asyncio.run(run_all())
    
    else:
        print(f"Unknown mode: {mode}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
