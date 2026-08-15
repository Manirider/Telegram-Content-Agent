"""Health check service with HTTP endpoint."""

import aiosqlite
from aiohttp import web

from app.config.settings import get_settings
from app.llm.orchestrator import LLMOrchestrator
from app.memory.sqlite_repository import SQLiteRepository
from app.sheets.client import SheetsClient
from app.utils.logging import get_logger

logger = get_logger(__name__)


class HealthService:
    """Health check service with HTTP endpoints."""
    
    def __init__(
        self,
        llm_orchestrator: LLMOrchestrator | None = None,
        sheets_client: SheetsClient | None = None,
        db_repository: SQLiteRepository | None = None,
    ):
        self.settings = get_settings()
        self.llm_orchestrator = llm_orchestrator
        self.sheets_client = sheets_client
        self.db_repository = db_repository
        self.app: web.Application | None = None
        self.runner: web.AppRunner | None = None
    
    def create_app(self) -> web.Application:
        """Create aiohttp application with health endpoints."""
        app = web.Application()
        app.router.add_get("/health", self.health_handler)
        app.router.add_get("/ready", self.ready_handler)
        app.router.add_get("/live", self.live_handler)
        return app
    
    async def health_handler(self, request: web.Request) -> web.Response:
        """Basic health check - process is alive."""
        return web.json_response({
            "status": "healthy",
            "service": "telegram-content-agent",
        })
    
    async def live_handler(self, request: web.Request) -> web.Response:
        """Liveness probe - process is running."""
        return web.json_response({"status": "alive"})
    
    async def ready_handler(self, request: web.Request) -> web.Response:
        """Readiness probe - critical dependencies initialized."""
        checks = {}
        overall_ready = True
        
        # Check database
        if self.db_repository:
            try:
                # Simple query to verify DB connectivity
                await self.db_repository.get_style(0)  # Will return None, but tests connection
                checks["database"] = "ok"
            except (OSError, RuntimeError, aiosqlite.Error) as e:
                checks["database"] = f"error: {e}"
                overall_ready = False
        else:
            checks["database"] = "not_configured"
        
        # Check Google Sheets (optional - don't fail if not ready)
        if self.sheets_client:
            try:
                if self.sheets_client.gc:
                    checks["sheets"] = "ok"
                else:
                    checks["sheets"] = "not_initialized"
            except (OSError, RuntimeError) as e:
                checks["sheets"] = f"error: {e}"
        else:
            checks["sheets"] = "not_configured"
        
        # Check LLM providers (optional - don't fail if not ready)
        if self.llm_orchestrator:
            try:
                health = await self.llm_orchestrator.health_check_all()
                checks["llm_providers"] = health  # type: ignore[assignment]
                # Don't mark as unready if LLM is down - we can still receive messages
            except (OSError, RuntimeError) as e:
                checks["llm_providers"] = f"error: {e}"
        else:
            checks["llm_providers"] = "not_configured"
        
        status_code = 200 if overall_ready else 503
        
        return web.json_response({
            "status": "ready" if overall_ready else "not_ready",
            "checks": checks,
        }, status=status_code)
    
    async def start(self) -> None:
        """Start health check HTTP server."""
        self.app = self.create_app()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        site = web.TCPSite(
            self.runner,
            self.settings.health_host,
            self.settings.health_port,
        )
        await site.start()
        
        logger.info(
            "Health check server started",
            host=self.settings.health_host,
            port=self.settings.health_port,
        )
    
    async def stop(self) -> None:
        """Stop health check server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")