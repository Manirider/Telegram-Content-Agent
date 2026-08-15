"""LLM Orchestrator with provider fallback."""
from app.config.settings import get_settings
from app.ingestion.models import NormalizedContent
from app.llm.base import LLMProvider
from app.llm.gemini_client import GeminiProvider
from app.llm.groq_client import GroqProvider
from app.llm.ollama_client import OllamaProvider
from app.llm.parser import repair_x_post, validate_generation_result
from app.llm.prompts import (
    build_correction_prompt,
    build_user_prompt,
    get_system_prompt,
)
from app.llm.schemas import ContentGenerationResult, LLMRequest
from app.memory.service import MemoryService
from app.utils.exceptions import (
    AuthenticationError,
    LLMError,
    LLMValidationError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.utils.logging import get_logger
from app.utils.retry import async_retry

logger = get_logger(__name__)


class LLMOrchestrator:
    """Orchestrate LLM providers with fallback and validation."""
    
    def __init__(self, memory_service: MemoryService):
        self.memory_service = memory_service
        self.settings = get_settings()
        self.providers: dict[str, LLMProvider] = {}
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize configured providers."""
        # Ollama (always available, may fail at runtime)
        self.providers["ollama"] = OllamaProvider()
        
        # Groq (if configured)
        if self.settings.groq_api_key:
            self.providers["groq"] = GroqProvider()
        
        # Gemini (if configured)
        if self.settings.gemini_api_key:
            self.providers["gemini"] = GeminiProvider()
        
        logger.info("LLM providers initialized", providers=list(self.providers.keys()))
    
    def _get_provider_order(self) -> list[str]:
        """Get provider order: primary first, then fallbacks."""
        primary = self.settings.llm_primary_provider.lower()
        fallbacks = [p.strip().lower() for p in self.settings.llm_fallback_providers.split(",")]
        
        order = [primary]
        for fb in fallbacks:
            if fb and fb != primary and fb in self.providers:
                order.append(fb)
        
        # Filter to only available providers
        return [p for p in order if p in self.providers]
    
    async def generate(
        self,
        content: NormalizedContent,
        user_id: int,
        request_id: str,
    ) -> ContentGenerationResult:
        """Generate content with provider fallback."""
        # Get user style
        style_prompt = await self.memory_service.get_style(user_id)
        style_hash = await self.memory_service.get_style_hash(user_id)
        
        logger.info(
            "Starting LLM generation",
            request_id=request_id,
            user_id=user_id,
            content_type=content.content_type.value,
            style_hash=style_hash[:16],
        )
        
        # Build prompts
        system_prompt = get_system_prompt()
        user_prompt = build_user_prompt(content, style_prompt)
        
        request = LLMRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        # Try providers in order
        provider_order = self._get_provider_order()
        last_error: BaseException | None = None
        
        for provider_name in provider_order:
            provider = self.providers[provider_name]
            
            logger.info("Trying provider", provider=provider_name, request_id=request_id)
            
            try:
                result = await self._generate_with_provider(provider, request, request_id)
                
                # Validate result
                validation_errors = validate_generation_result(result)
                if validation_errors:
                    # Try to repair X post if only issue is length
                    if len(validation_errors) == 1 and "exceeds 280" in validation_errors[0]:
                        repaired_x = repair_x_post(
                            result.variants.x_post,
                            result.variants.linkedin_post,
                        )
                        # Create new result with repaired X post
                        from app.llm.schemas import Variants
                        result = ContentGenerationResult(
                            title=result.title,
                            rationale=result.rationale,
                            category=result.category,
                            variants=Variants(
                                x_post=repaired_x,
                                linkedin_post=result.variants.linkedin_post,
                            ),
                        )
                        validation_errors = validate_generation_result(result)
                    
                    if validation_errors:
                        logger.warning(
                            "Validation failed, trying correction",
                            provider=provider_name,
                            errors=validation_errors,
                            request_id=request_id,
                        )
                        # Try one correction attempt
                        result = await self._correct_with_provider(
                            provider, request, result, validation_errors, request_id
                        )
                        validation_errors = validate_generation_result(result)
                        if validation_errors:
                            raise LLMValidationError(f"Validation failed after correction: {validation_errors}")
                
                logger.info(
                    "LLM generation successful",
                    provider=provider_name,
                    request_id=request_id,
                    title_length=len(result.title),
                    x_length=len(result.variants.x_post),
                    linkedin_length=len(result.variants.linkedin_post),
                )
                return result
                
            except (ProviderUnavailableError, RateLimitError, AuthenticationError, LLMValidationError) as e:
                last_error = e
                logger.warning(
                    "Provider failed, trying next",
                    provider=provider_name,
                    error=str(e),
                    request_id=request_id,
                )
                continue
            except (OSError, RuntimeError, ValueError) as e:
                last_error = e
                logger.error(
                    "Unexpected provider error",
                    provider=provider_name,
                    error=str(e),
                    request_id=request_id,
                )
                continue
        
        # All providers failed
        raise LLMError(f"All LLM providers failed. Last error: {last_error}")
    
    async def _generate_with_provider(
        self,
        provider: LLMProvider,
        request: LLMRequest,
        request_id: str,
    ) -> ContentGenerationResult:
        """Generate with a specific provider with retry."""
        return await async_retry(
            provider.generate,
            request,
            max_attempts=self.settings.max_retries,
            base_delay=self.settings.retry_base_delay,
            max_delay=self.settings.retry_max_delay,
            jitter=self.settings.retry_jitter,
        )
    
    async def _correct_with_provider(
        self,
        provider: LLMProvider,
        original_request: LLMRequest,
        failed_result: ContentGenerationResult,
        validation_errors: list[str],
        request_id: str,
    ) -> ContentGenerationResult:
        """Attempt to correct invalid output with a follow-up prompt."""
        correction_prompt = build_correction_prompt(
            failed_result.model_dump_json(),
            validation_errors,
        )
        
        correction_request = LLMRequest(
            system_prompt=original_request.system_prompt,
            user_prompt=correction_prompt,
        )
        
        return await provider.generate(correction_request)
    
    async def health_check_all(self) -> dict[str, bool]:
        """Check health of all providers."""
        results = {}
        for name, provider in self.providers.items():
            try:
                results[name] = await provider.health_check()
            except (OSError, RuntimeError, ValueError):
                results[name] = False
        return results
    
    async def close(self) -> None:
        """Close all providers."""
        for provider in self.providers.values():
            try:
                await provider.close()
            except (OSError, RuntimeError) as e:
                logger.warning("Error closing provider", error=str(e))