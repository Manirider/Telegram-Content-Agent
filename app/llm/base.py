"""Base LLM provider interface."""
from abc import ABC, abstractmethod

from app.llm.schemas import ContentGenerationResult, LLMRequest
from app.utils.exceptions import (
    AuthenticationError,
    LLMError,
    ProviderUnavailableError,
    RateLimitError,
)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
    
    @abstractmethod
    async def generate(self, request: LLMRequest) -> ContentGenerationResult:
        """Generate structured content."""
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    @abstractmethod
    async def close(self) -> None:
        """Close provider connections."""
    
    def _classify_error(self, error: Exception) -> LLMError:
        """Classify error for retry logic."""
        error_str = str(error).lower()
        
        if "rate limit" in error_str or "429" in error_str:
            return RateLimitError(f"{self.name} rate limited: {error}")
        if "unauthorized" in error_str or "401" in error_str or "api key" in error_str:
            return AuthenticationError(f"{self.name} authentication failed: {error}")
        if "forbidden" in error_str or "403" in error_str:
            return AuthenticationError(f"{self.name} access forbidden: {error}")
        if "timeout" in error_str or "timed out" in error_str:
            return ProviderUnavailableError(f"{self.name} timeout: {error}")
        if "connection" in error_str or "connect" in error_str:
            return ProviderUnavailableError(f"{self.name} connection failed: {error}")
        if "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
            return ProviderUnavailableError(f"{self.name} server error: {error}")
        
        return LLMError(f"{self.name} error: {error}")