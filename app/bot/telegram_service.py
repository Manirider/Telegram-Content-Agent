"""Telegram service wrapper."""

from telegram import Bot, Message
from telegram.ext import Application, ApplicationBuilder

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class TelegramService:
    """Wrapper for Telegram bot operations."""
    
    def __init__(self, token: str | None = None):
        self.settings = get_settings()
        self.token = token or self.settings.telegram_bot_token
        self.application: Application | None = None
        self.bot: Bot | None = None
    
    async def initialize(self) -> Application:
        """Initialize Telegram application."""
        if not self.token:
            raise ValueError("Telegram bot token not configured")
        
        self.application = (
            ApplicationBuilder()
            .token(self.token)
            .build()
        )
        self.bot = self.application.bot
        
        logger.info("Telegram application initialized")
        return self.application
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
    ) -> Message | None:
        """Send a message."""
        if not self.bot:
            raise RuntimeError("Telegram service not initialized")
        
        try:
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
            )
            return message
        except Exception as e:
            logger.error("Failed to send message", chat_id=chat_id, error=str(e))
            raise
    
    async def start_polling(self) -> None:
        """Start long polling."""
        if not self.application:
            await self.initialize()
        
        logger.info("Starting Telegram long polling")
        await self.application.initialize()  # type: ignore[union-attr]
        await self.application.start()  # type: ignore[union-attr]
        await self.application.updater.start_polling(  # type: ignore[union-attr]
            drop_pending_updates=True,
            allowed_updates=["message", "edited_message"],
        )
    
    async def stop(self) -> None:
        """Stop the bot."""
        if self.application:
            await self.application.updater.stop()  # type: ignore[union-attr]
            await self.application.stop()  # type: ignore[union-attr]
            await self.application.shutdown()  # type: ignore[union-attr]
            logger.info("Telegram bot stopped")
