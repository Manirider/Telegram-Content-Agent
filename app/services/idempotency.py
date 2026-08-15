"""Idempotency service."""
from app.ingestion.models import NormalizedContent
from app.memory.service import MemoryService
from app.memory.sqlite_repository import SQLiteRepository
from app.utils.hashing import content_fingerprint
from app.utils.logging import get_logger

logger = get_logger(__name__)


class IdempotencyService:
    """Service for idempotency checking and management."""
    
    def __init__(
        self,
        idempotency_repo: SQLiteRepository,
        memory_service: MemoryService,
    ):
        self.idempotency_repo = idempotency_repo
        self.memory_service = memory_service
    
    async def check_and_reserve(
        self,
        content: NormalizedContent,
        user_id: int,
    ) -> tuple[bool, str]:
        """
        Check if content is duplicate and reserve if not.
        
        Returns: (is_new, fingerprint)
        """
        user_style_hash = await self.memory_service.get_style_hash(user_id)
        
        fingerprint = content_fingerprint(
            content.source_identifier,
            content.content_hash,
            user_style_hash,
        )
        
        reserved = await self.idempotency_repo.reserve_fingerprint(
            fingerprint=fingerprint,
            user_id=user_id,
            source_identifier=content.source_identifier,
            content_hash=content.content_hash,
            style_hash=user_style_hash,
        )
        
        return reserved, fingerprint
    
    async def mark_completed(self, fingerprint: str) -> None:
        await self.idempotency_repo.mark_completed(fingerprint)
    
    async def mark_failed(self, fingerprint: str) -> None:
        await self.idempotency_repo.mark_failed(fingerprint)
    
    async def cleanup_stale(self, max_age_hours: int = 24) -> int:
        return await self.idempotency_repo.cleanup_stale_processing(max_age_hours)