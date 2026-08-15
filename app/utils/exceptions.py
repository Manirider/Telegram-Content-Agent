"""Application-specific exceptions."""


class AppError(Exception):
    """Base application error."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(AppError):
    """Configuration error."""


class IngestionError(AppError):
    """Content ingestion error."""


class ExtractionError(AppError):
    """Content extraction error."""


class UnsupportedContentError(IngestionError):
    """Unsupported content type error."""


class EmptyContentError(IngestionError):
    """Empty content error."""


class ContentTooLargeError(IngestionError):
    """Content exceeds size limits."""


class LLMError(AppError):
    """LLM-related error."""


class LLMValidationError(LLMError):
    """LLM output validation error."""


class ProviderUnavailableError(LLMError):
    """LLM provider unavailable."""


class RateLimitError(LLMError):
    """Rate limit exceeded."""


class AuthenticationError(LLMError):
    """Authentication failed."""


class SheetsError(AppError):
    """Google Sheets error."""


class DuplicateContentError(AppError):
    """Duplicate content detected."""
    def __init__(self, message: str, fingerprint: str, details: dict | None = None):
        super().__init__(message, details)
        self.fingerprint = fingerprint


class IdempotencyError(AppError):
    """Idempotency check error."""


class ValidationError(AppError):
    """Business validation error."""


class HealthCheckError(AppError):
    """Health check error."""
