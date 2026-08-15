"""Ollama LLM provider."""
import json

import ollama

from app.config.settings import get_settings
from app.llm.base import LLMProvider
from app.llm.schemas import ContentGenerationResult, LLMRequest
from app.utils.exceptions import LLMValidationError, ProviderUnavailableError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""
    
    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.settings = get_settings()
        self.base_url = base_url or self.settings.ollama_base_url
        self.model = model or self.settings.ollama_model
        self.client: ollama.AsyncClient | None = None
        self._timeout = self.settings.ollama_timeout_seconds
    
    @property
    def name(self) -> str:
        return "ollama"
    
    async def _get_client(self) -> ollama.AsyncClient:
        if self.client is None:
            self.client = ollama.AsyncClient(host=self.base_url, timeout=self._timeout)
        return self.client
    
    async def generate(self, request: LLMRequest) -> ContentGenerationResult:
        """Generate content using Ollama."""
        client = await self._get_client()
        
        try:
            # Combine system and user prompts
            full_prompt = f"{request.system_prompt}\n\n{request.user_prompt}"
            
            response = await client.generate(
                model=self.model,
                prompt=full_prompt,
                options={
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                },
                format="json",  # Request JSON output
            )
            
            content = response.get("response", "")
            
            if not content:
                raise LLMValidationError("Empty response from Ollama")
            
            # Parse JSON response
            return self._parse_response(content)
            
        except ollama.ResponseError as e:
            if "model not found" in str(e).lower():
                raise ProviderUnavailableError(f"Ollama model not found: {self.model}") from e
            raise ProviderUnavailableError(f"Ollama error: {e}") from e
        except Exception as e:
            raise self._classify_error(e) from e
    
    def _parse_response(self, content: str) -> ContentGenerationResult:
        """Parse and validate JSON response."""
        # Try direct JSON parse
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown fences
            data = self._extract_json(content)
        
        # Validate with Pydantic
        try:
            return ContentGenerationResult(**data)
        except Exception as e:
            raise LLMValidationError(f"Invalid response format: {e}") from e
    
    def _extract_json(self, content: str) -> dict:
        """Extract JSON from markdown code fences or mixed content."""
        import re
        
        # Try markdown fenced JSON
        fence_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(fence_pattern, content, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # Try to find JSON object in content
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, content, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        raise LLMValidationError("No valid JSON found in response")
    
    async def health_check(self) -> bool:
        """Check if Ollama is available and model exists."""
        try:
            client = await self._get_client()
            # List models to check connectivity
            models = await client.list()
            model_names = [m.get("name", "") for m in models.get("models", [])]
            
            # Check if our model is available (with or without tag)
            model_base = self.model.split(":")[0]
            available = any(model_base in name for name in model_names)
            
            if not available:
                logger.warning("Ollama model not available", model=self.model, available=models)
            
            return available
        except (OSError, RuntimeError, ollama.ResponseError) as e:
            logger.warning("Ollama health check failed", error=str(e))
            return False
    
    async def close(self) -> None:
        """Close client."""
        if self.client:
            # ollama client doesn't have explicit close
            self.client = None