"""Gemini LLM provider."""
import json

import google.generativeai as genai

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


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider."""
    
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.settings = get_settings()
        self.api_key = api_key or self.settings.gemini_api_key
        self.model_name = model or self.settings.gemini_model
        self.timeout = self.settings.gemini_timeout_seconds
        self.model: genai.GenerativeModel | None = None
    
    @property
    def name(self) -> str:
        return "gemini"
    
    def _configure(self) -> None:
        if not self.api_key:
            raise AuthenticationError("Gemini API key not configured")
        genai.configure(api_key=self.api_key)
    
    def _get_model(self) -> genai.GenerativeModel:
        if self.model is None:
            self._configure()
            self.model = genai.GenerativeModel(
                self.model_name,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                ),
            )
        return self.model
    
    async def generate(self, request: LLMRequest) -> ContentGenerationResult:
        """Generate content using Gemini."""
        if not self.api_key:
            raise AuthenticationError("Gemini API key not configured")
        
        model = self._get_model()
        
        try:
            # Combine prompts for Gemini
            full_prompt = f"{request.system_prompt}\n\n{request.user_prompt}"
            
            response = await model.generate_content_async(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=request.temperature,
                    max_output_tokens=request.max_tokens,
                    response_mime_type="application/json",
                ),
            )
            
            content = response.text
            
            if not content:
                raise LLMValidationError("Empty response from Gemini")
            
            return self._parse_response(content)
            
        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str:
                raise RateLimitError("Gemini rate limit exceeded") from e
            if "api key" in error_str or "unauthorized" in error_str or "401" in error_str:
                raise AuthenticationError("Gemini authentication failed") from e
            if "forbidden" in error_str or "403" in error_str:
                raise AuthenticationError("Gemini access forbidden") from e
            if "timeout" in error_str:
                raise ProviderUnavailableError("Gemini timeout") from e
            if "500" in error_str or "503" in error_str:
                raise ProviderUnavailableError("Gemini server error") from e
            
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
        """Check if Gemini is available."""
        if not self.api_key:
            return False
        
        try:
            self._configure()
            # List models to verify connectivity
            _ = genai.list_models()
            return True
        except (OSError, RuntimeError) as e:
            logger.warning("Gemini health check failed", error=str(e))
            return False
    
    async def close(self) -> None:
        """Close - no persistent connections for Gemini."""
        self.model = None