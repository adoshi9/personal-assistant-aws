"""FastAPI gateway application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import structlog

from app.config import get_settings
from app.bot import TelegramBot

logger = structlog.get_logger(__name__)


# Global bot instance
telegram_bot: TelegramBot | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan context manager."""
    global telegram_bot

    # Startup
    logger.info("Starting application")
    try:
        # Initialize and start Telegram bot
        telegram_bot = TelegramBot()
        await telegram_bot.initialize()
        await telegram_bot.start()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down application")
    if telegram_bot:
        await telegram_bot.stop()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI app
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Secure Personal AI Assistant for AWS",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/")
    async def root() -> JSONResponse:
        """Root endpoint."""
        return JSONResponse(
            {
                "service": settings.app_name,
                "version": "0.1.0",
                "status": "running",
                "environment": settings.app_env,
            }
        )

    @app.get("/health")
    async def health() -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "healthy", "bot": telegram_bot is not None})

    @app.get("/status")
    async def status() -> JSONResponse:
        """Status endpoint with detailed information."""
        return JSONResponse(
            {
                "status": "operational",
                "environment": settings.app_env,
                "region": settings.aws_region,
                "model": settings.anthropic_model,
                "telegram_bot": telegram_bot is not None,
            }
        )

    # Error handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc: Exception) -> JSONResponse:
        """Global exception handler."""
        logger.error("Unhandled exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "message": str(exc)},
        )

    return app
