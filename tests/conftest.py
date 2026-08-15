"""Pytest configuration and fixtures for testing."""
import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def setup_test_env():
    """Set up test environment variables before any tests run."""
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token_123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    os.environ.setdefault("GOOGLE_SHEETS_CREDENTIALS_B64", "eyJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsICJwcm9qZWN0X2lkIjogInRlc3QtcHJvamVjdCIsICJwcml2YXRlX2tleV9pZCI6ICJ0ZXN0LWtleSIsICJwcml2YXRlX2tleSI6ICItLS0tLUJFR0lOIFBSSVZBVEUgS0VZLS0tLS0KIn0=")
    os.environ.setdefault("GOOGLE_SHEETS_SPREADSHEET_ID", "test_spreadsheet_id")
    os.environ.setdefault("DATABASE_PATH", ":memory:")
    os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
    os.environ.setdefault("OLLAMA_MODEL", "llama3.1")
    os.environ.setdefault("GROQ_API_KEY", "")
    os.environ.setdefault("GEMINI_API_KEY", "")
    os.environ.setdefault("LLM_PRIMARY_PROVIDER", "ollama")
    os.environ.setdefault("LLM_FALLBACK_PROVIDERS", "groq,gemini")
    os.environ.setdefault("HTTP_TIMEOUT_SECONDS", "30")
    os.environ.setdefault("MAX_TEXT_LENGTH", "50000")
    os.environ.setdefault("MAX_PDF_SIZE_MB", "50")
    os.environ.setdefault("MAX_URL_CONTENT_LENGTH", "100000")
    os.environ.setdefault("MAX_RETRIES", "3")
    os.environ.setdefault("RETRY_BASE_DELAY", "1.0")
    os.environ.setdefault("RETRY_MAX_DELAY", "60.0")
    os.environ.setdefault("RETRY_JITTER", "0.1")
    os.environ.setdefault("LOG_LEVEL", "DEBUG")
    os.environ.setdefault("HEALTH_HOST", "0.0.0.0")
    os.environ.setdefault("HEALTH_PORT", "8080")
    os.environ.setdefault("MAX_STYLE_LENGTH", "2000")


@pytest.fixture
def reset_settings_cache():
    """Reset the settings cache for each test."""
    from app.config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()