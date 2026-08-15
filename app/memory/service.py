"""Memory service for style management."""

from app.config.settings import get_settings
from app.memory.sqlite_repository import SQLiteRepository
from app.utils.exceptions import ValidationError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MemoryService:
    """Service for managing user style memory."""
    
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository
        self.settings = get_settings()
    
    async def get_style(self, user_id: int) -> str | None:
        """Get user's style prompt."""
        style = await self.repository.get_style(user_id)
        return style.style_prompt if style else None
    
    async def set_style(self, user_id: int, style_prompt: str) -> str:
        """Set user's style prompt with validation."""
        style_prompt = style_prompt.strip()
        
        if not style_prompt:
            raise ValidationError("Style prompt cannot be empty")
        
        if len(style_prompt) > self.settings.max_style_length:
            raise ValidationError(
                f"Style prompt too long (max {self.settings.max_style_length} characters)"
            )
        
        await self.repository.set_style(user_id, style_prompt)
        logger.info("Style set", user_id=user_id, length=len(style_prompt))
        return style_prompt
    
    async def clear_style(self, user_id: int) -> bool:
        """Clear user's style prompt."""
        result = await self.repository.clear_style(user_id)
        logger.info("Style cleared", user_id=user_id, existed=result)
        return result
    
    async def get_style_hash(self, user_id: int) -> str:
        """Get hash of user's style for idempotency."""
        from app.utils.hashing import style_hash
        style = await self.get_style(user_id)
        return style_hash(style)