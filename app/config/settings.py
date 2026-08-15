from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Port (Render, Heroku, Cloud Run inject PORT)
    port: int | None = Field(default=None, validation_alias="PORT", description="Port injected by host")

    # Telegram
    telegram_bot_token: str = Field(..., description="Telegram Bot Token from BotFather")

    # Google Sheets
    google_sheets_credentials_b64: str = Field(default="", description="Base64 encoded Google Service Account JSON")
    google_sheets_spreadsheet_id: str = Field(default="", description="Google Spreadsheet ID")
    google_sheets_worksheet: str = Field(default="Content", description="Worksheet name")

    # Ollama
    ollama_base_url: str = Field(default="http://ollama:11434", description="Ollama base URL")
    ollama_model: str = Field(default="llama3.1", description="Ollama model name")
    ollama_timeout_seconds: int = Field(default=120, description="Ollama request timeout")

    # Groq
    groq_api_key: str | None = Field(default=None, description="Groq API Key")
    groq_model: str = Field(default="llama-3.1-70b-versatile", description="Groq model name")
    groq_timeout_seconds: int = Field(default=60, description="Groq request timeout")

    # Gemini
    gemini_api_key: str | None = Field(default=None, description="Gemini API Key")
    gemini_model: str = Field(default="gemini-1.5-flash", description="Gemini model name")
    gemini_timeout_seconds: int = Field(default=60, description="Gemini request timeout")

    # LLM Routing
    llm_primary_provider: str = Field(default="ollama", description="Primary LLM provider: ollama, groq, gemini")
    llm_fallback_providers: str = Field(default="groq,gemini", description="Comma-separated fallback providers")

    # Database
    database_path: str = Field(default="/data/style_memory.db", description="SQLite database path")

    # HTTP
    http_timeout_seconds: int = Field(default=30, description="HTTP request timeout")
    http_max_redirects: int = Field(default=5, description="Maximum HTTP redirects")

    # Content Limits
    max_text_length: int = Field(default=50000, description="Maximum text length for processing")
    max_pdf_size_mb: int = Field(default=50, description="Maximum PDF file size in MB")
    max_url_content_length: int = Field(default=100000, description="Maximum URL content length")

    # Retry
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_base_delay: float = Field(default=1.0, description="Base delay for exponential backoff")
    retry_max_delay: float = Field(default=60.0, description="Maximum delay for retries")
    retry_jitter: float = Field(default=0.1, description="Jitter factor for retries")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Health
    health_host: str = Field(default="0.0.0.0", description="Health check host")
    health_port: int = Field(default=8080, description="Health check port")

    # Style
    max_style_length: int = Field(default=2000, description="Maximum style prompt length")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]