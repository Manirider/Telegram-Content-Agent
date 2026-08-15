"""Groq LLM provider."""
import json

import httpx

from app.config.settings import get_settings
from app.llm.base import LLMProvider
from app.llm.schemas import ContentGenerationResult, LLMRequest
from app.utils.exceptions import (
    AuthenticationError,
    LLMValidationError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GroqProvider(LLMProvider):
    """Groq cloud LLM provider."""
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.settings = get_settings()
        self.api_key = api_key or self.settings.groq_api_key
        self.model = model or self.settings.groq_model
        self.timeout = self.settings.groq_timeout_seconds
        self.client: httpx.AsyncClient | None = None
        self.base_url = "https://api.groq.com/openai/v1"
    
    @property
    def name(self) -> str:
        return "groq"
    
    def _get_headers(self) -> dict:
        if not self.api_key:
            raise AuthenticationError("Groq API key not configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=httpx.Timeout(self.timeout),
            )
        return self.client
    
    async def generate(self, request: LLMRequest) -> ContentGenerationResult:
        """Generate content using Groq."""
        if not self.api_key:
            raise AuthenticationError("Groq API key not configured")
        
        client = await self._get_client()
        
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "response_format": {"type": "json_object"},
            }
            
            response = await client.post("/chat/completions", json=payload)
            
            if response.status_code == 429:
                raise RateLimitError("Groq rate limit exceeded")
            if response.status_code == 401:
                raise AuthenticationError("Groq authentication failed")
            if response.status_code == 403:
                raise AuthenticationError("Groq access forbidden")
            if response.status_code >= 500:
                raise ProviderUnavailableError(f"Groq server error: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if not content:
                raise LLMValidationError("Empty response from Groq")
            
            return self._parse_response(content)
            
        except httpx.TimeoutException as e:
            raise ProviderUnavailableError("Groq timeout") from e
        except httpx.RequestError as e:
            raise ProviderUnavailableError(f"Groq request failed: {e}") from e
        except (RateLimitError, AuthenticationError, ProviderUnavailableError):
            raise
        except Exception as e:
            raise self._classify_error(e) from e
    
    def _parse_response(self, content: str) -> ContentGenerationResult:
        """Parse and validate JSON response."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = self._extract_json(content)
        
        try:
            return ContentGenerationResult(**data)
        except Exception as e:
            raise LLMValidationError(f"Invalid response format: {e}") from e
    
    def _extract_json(self, content: str) -> dict:
        """Extract JSON from markdown code fences or mixed content."""
        import re
        
        fence_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(fence_pattern, content, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, content, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        raise LLMValidationError("No valid JSON found in response")
    
    async def health_check(self) -> bool:
        """Check if Groq is available."""
        if not self.api_key:
            return False
        
        try:
            client = await self._get_client()
            response = await client.get("/models")
            return response.status_code == 200
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning("Groq health check failed", error=str(e))
            return False
    
    async def close(self) -> None:
        """Close client."""
        if self.client and not self.client.is_closed:
            await self.client.aclose()
        self.client = None