"""Main application entry point."""
import asyncio
import signal

from app.bot.handlers import BotHandlers
from app.bot.telegram_service import TelegramService
from app.config.settings import get_settings
from app.health.service import HealthService
from app.ingestion.router import ContentRouter
from app.llm.orchestrator import LLMOrchestrator
from app.memory.service import MemoryService
from app.memory.sqlite_repository import SQLiteRepository
from app.services.content_service import ContentService
from app.sheets.client import SheetsClient
from app.sheets.repository import SheetsRepository
from app.sheets.schemas import SheetsConfig
from app.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


class Application:
    """Main application class."""
    
    def __init__(self):
        self.settings = get_settings()
        configure_logging(self.settings.log_level)
        
        # Components
        self.db_repository: SQLiteRepository | None = None
        self.memory_service: MemoryService | None = None
        self.content_router: ContentRouter | None = None
        self.llm_orchestrator: LLMOrchestrator | None = None
        self.sheets_client: SheetsClient | None = None
        self.sheets_repository: SheetsRepository | None = None
        self.telegram_service: TelegramService | None = None
        self.bot_handlers: BotHandlers | None = None
        self.content_service: ContentService | None = None
        self.health_service: HealthService | None = None
        
        self._shutdown_event = asyncio.Event()
    
    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing application")
        
        # Database
        self.db_repository = SQLiteRepository(self.settings.database_path)
        await self.db_repository.initialize()
        
        # Memory service
        self.memory_service = MemoryService(self.db_repository)
        
        # Content router
        self.content_router = ContentRouter()
        
        # LLM orchestrator
        self.llm_orchestrator = LLMOrchestrator(self.memory_service)
        
        # Google Sheets
        if self.settings.google_sheets_credentials_b64 and self.settings.google_sheets_spreadsheet_id:
            try:
                sheets_config = SheetsConfig(
                    credentials_b64=self.settings.google_sheets_credentials_b64,
                    spreadsheet_id=self.settings.google_sheets_spreadsheet_id,
                    worksheet_name=self.settings.google_sheets_worksheet,
                )
                self.sheets_client = SheetsClient(sheets_config)
                self.sheets_repository = SheetsRepository(self.sheets_client)
                await self.sheets_repository.initialize()
                logger.info("Google Sheets initialized successfully")
            except Exception as e:
                logger.warning("Google Sheets initialization failed (running without sheets)", error=str(e))
                self.sheets_client = None
                self.sheets_repository = None
        else:
            logger.info("Google Sheets not configured - running without sheets integration")
            self.sheets_client = None
            self.sheets_repository = None
        
        # Content service
        self.content_service = ContentService(
            router=self.content_router,
            llm_orchestrator=self.llm_orchestrator,
            memory_service=self.memory_service,
            sheets_repository=self.sheets_repository,
            idempotency_repo=self.db_repository,
        )
        
        # Telegram
        self.telegram_service = TelegramService()
        await self.telegram_service.initialize()
        
        self.bot_handlers = BotHandlers(
            telegram_service=self.telegram_service,
            content_service=self.content_service,
            memory_service=self.memory_service,
        )
        
        # Register handlers
        for handler in self.bot_handlers.get_handlers():
            self.telegram_service.application.add_handler(handler)  # type: ignore[union-attr]
        
        # Health check
        self.health_service = HealthService(
            llm_orchestrator=self.llm_orchestrator,
            sheets_client=self.sheets_client,
            db_repository=self.db_repository,
        )
        await self.health_service.start()
        
        logger.info("Application initialized successfully")
    
    async def start(self) -> None:
        """Start the application."""
        logger.info("Starting application")
        
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._shutdown_event.set)
            except NotImplementedError:
                # Windows doesn't support signal handlers
                pass
        
        # Start Telegram polling
        await self.telegram_service.start_polling()  # type: ignore[union-attr]
        
        logger.info("Application started - waiting for shutdown signal")
        
        # Wait for shutdown
        await self._shutdown_event.wait()
    
    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down application")
        
        # Stop Telegram
        if self.telegram_service:
            await self.telegram_service.stop()
        
        # Stop health check
        if self.health_service:
            await self.health_service.stop()
        
        # Close content service
        if self.content_service:
            await self.content_service.close()
        
        # Close database
        if self.db_repository:
            await self.db_repository.close()
        
        logger.info("Application shutdown complete")
    
    async def run(self) -> None:
        """Run the application."""
        try:
            await self.initialize()
            await self.start()
        except Exception as e:
            logger.error("Application error", error=str(e))
            raise
        finally:
            await self.shutdown()


async def main() -> None:
    """Main entry point."""
    app = Application()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())