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
        """Create aiohttp application with health and dashboard endpoints."""
        app = web.Application()
        app.router.add_get("/", self.home_handler)
        app.router.add_get("/health", self.health_handler)
        app.router.add_get("/ready", self.ready_handler)
        app.router.add_get("/live", self.live_handler)
        return app
    
    async def home_handler(self, request: web.Request) -> web.Response:
        """Serve sleek live project landing page."""
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Content Agent — Live</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #090d16;
            --card-bg: rgba(255, 255, 255, 0.03);
            --card-border: rgba(255, 255, 255, 0.08);
            --primary: #0088cc;
            --accent: #00d2ff;
            --success: #10b981;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Outfit', sans-serif;
            background: radial-gradient(circle at 50% 0%, #172554 0%, #090d16 65%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
        }
        .container { max-width: 900px; width: 100%; }
        .header { text-align: center; margin-bottom: 40px; }
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 16px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 9999px;
            color: var(--success);
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 20px;
        }
        .badge-dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; box-shadow: 0 0 10px var(--success); }
        h1 {
            font-size: 2.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, #ffffff 0%, #93c5fd 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px;
        }
        p.subtitle { color: var(--text-muted); font-size: 1.15rem; max-width: 600px; margin: 0 auto; line-height: 1.6; }
        .actions { display: flex; justify-content: center; gap: 16px; margin-top: 24px; flex-wrap: wrap; }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 12px 28px;
            border-radius: 12px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
        }
        .btn-primary { background: linear-gradient(135deg, #0088cc, #00d2ff); color: #fff; box-shadow: 0 4px 20px rgba(0, 136, 204, 0.4); }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(0, 136, 204, 0.6); }
        .btn-secondary { background: var(--card-bg); border: 1px solid var(--card-border); color: #fff; }
        .btn-secondary:hover { background: rgba(255, 255, 255, 0.08); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; margin: 40px 0; }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(12px);
        }
        .card h3 { font-size: 1.2rem; margin-bottom: 10px; color: #60a5fa; }
        .card p { color: var(--text-muted); font-size: 0.95rem; line-height: 1.5; }
        .mono { font-family: 'JetBrains Mono', monospace; background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }
        .endpoint-box { background: rgba(0, 0, 0, 0.3); border: 1px solid var(--card-border); border-radius: 12px; padding: 20px; margin-top: 20px; }
        .endpoint-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .endpoint-row:last-child { border-bottom: none; }
        footer { margin-top: 60px; text-align: center; color: var(--text-muted); font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="badge"><span class="badge-dot"></span> System Live & Operational</div>
            <h1>Telegram Content Agent</h1>
            <p class="subtitle">Autonomous AI agent that ingests multi-format content, applies persistent memory styles, and syncs idempotently with Google Sheets.</p>
            
            <div class="actions">
                <a href="https://github.com/Manirider/Telegram-Content-Agent" target="_blank" class="btn btn-secondary">
                    GitHub Repository
                </a>
                <a href="/ready" class="btn btn-secondary">
                    System Diagnostics
                </a>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Multi-Format Ingestion</h3>
                <p>Accepts raw text, article URLs (trafilatura), and PDF documents (MarkItDown) directly through Telegram.</p>
            </div>
            <div class="card">
                <h3>Style Memory</h3>
                <p>Personalized user writing styles persisted in SQLite. Configured dynamically with <span class="mono">/setstyle</span>.</p>
            </div>
            <div class="card">
                <h3>LLM Orchestration</h3>
                <p>High-resilience fallback pipeline across Groq, Google Gemini, and local Ollama models.</p>
            </div>
        </div>

        <div class="endpoint-box">
            <h4 style="margin-bottom: 12px;">Live Endpoints</h4>
            <div class="endpoint-row">
                <span>Liveness Probe</span>
                <a href="/health" class="mono" style="color: #38bdf8; text-decoration: none;">GET /health</a>
            </div>
            <div class="endpoint-row">
                <span>Readiness & Services Check</span>
                <a href="/ready" class="mono" style="color: #38bdf8; text-decoration: none;">GET /ready</a>
            </div>
            <div class="endpoint-row">
                <span>Kubernetes Live Check</span>
                <a href="/live" class="mono" style="color: #38bdf8; text-decoration: none;">GET /live</a>
            </div>
        </div>

        <footer>
            Built by <strong>MANIKANTA SURYASAI</strong> &bull; MIT License
        </footer>
    </div>
</body>
</html>"""
        return web.Response(text=html_content, content_type="text/html")
    
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