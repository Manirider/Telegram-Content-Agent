"""Content processing service - orchestrates the full pipeline."""
import uuid

from app.config.settings import get_settings
from app.ingestion.models import ContentInput
from app.ingestion.router import ContentRouter
from app.llm.orchestrator import LLMOrchestrator
from app.llm.schemas import ContentGenerationResult
from app.memory.service import MemoryService
from app.memory.sqlite_repository import SQLiteRepository
from app.sheets.repository import SheetsRepository
from app.utils.exceptions import (
    DuplicateContentError,
    IngestionError,
)
from app.utils.hashing import content_fingerprint
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ContentService:
    """Orchestrates content processing pipeline."""
    
    def __init__(
        self,
        router: ContentRouter,
        llm_orchestrator: LLMOrchestrator,
        memory_service: MemoryService,
        sheets_repository: SheetsRepository | None = None,
        idempotency_repo: SQLiteRepository | None = None,
    ):
        self.router = router
        self.llm_orchestrator = llm_orchestrator
        self.memory_service = memory_service
        self.sheets_repository = sheets_repository
        self.idempotency_repo = idempotency_repo
        self.settings = get_settings()
    
    async def process_content(
        self,
        content_input: ContentInput,
    ) -> tuple[bool, str, ContentGenerationResult | None]:
        """
        Process content through full pipeline.
        
        Returns: (is_new, fingerprint, generation_result)
        - is_new: True if new row inserted, False if duplicate
        - fingerprint: Idempotency fingerprint
        - generation_result: The generated content (None if duplicate)
        """
        request_id = str(uuid.uuid4())[:8]
        user_id = content_input.user_id
        
        logger.info(
            "Processing content",
            request_id=request_id,
            user_id=user_id,
            message_id=content_input.message_id,
        )
        
        # Step 1: Route and normalize content
        try:
            normalized = await self.router.route(content_input)
        except Exception as e:
            logger.error("Content routing failed", request_id=request_id, error=str(e))
            raise IngestionError(f"Failed to process content: {e}") from e
        
        # Step 2: Get style hash for idempotency
        style_hash = await self.memory_service.get_style_hash(user_id)
        
        # Step 3: Calculate fingerprint
        fingerprint = content_fingerprint(
            normalized.source_identifier,
            normalized.content_hash,
            style_hash,
        )
        
        # Step 4: Reserve fingerprint in local idempotency store
        reserved = await self.idempotency_repo.reserve_fingerprint(
            fingerprint=fingerprint,
            user_id=user_id,
            source_identifier=normalized.source_identifier,
            content_hash=normalized.content_hash,
            style_hash=style_hash,
        )
        
        if not reserved:
            # Already processed (COMPLETED status)
            logger.info("Duplicate content (local)", request_id=request_id, fingerprint=fingerprint[:16])
            await self.idempotency_repo.mark_failed(fingerprint)  # Clean up our reservation attempt
            raise DuplicateContentError(
                "This content with your current style was already processed.",
                fingerprint=fingerprint,
            )
        
        try:
            # Step 5: Generate content via LLM
            generation_result = await self.llm_orchestrator.generate(
                content=normalized,
                user_id=user_id,
                request_id=request_id,
            )
            
            # Step 6: Save to Google Sheets (if configured)
            if self.sheets_repository:
                is_new, _saved_fingerprint = await self.sheets_repository.save(
                    content=normalized,
                    result=generation_result,
                    style_hash=style_hash,
                )
                
                if not is_new:
                    # Race condition - another request beat us
                    if self.idempotency_repo:
                        await self.idempotency_repo.mark_failed(fingerprint)
                    raise DuplicateContentError(
                        "This content with your current style was already processed.",
                        fingerprint=fingerprint,
                    )
            
            # Step 7: Mark completed
            if self.idempotency_repo:
                await self.idempotency_repo.mark_completed(fingerprint)
            
            logger.info(
                "Content processing complete",
                request_id=request_id,
                fingerprint=fingerprint[:16],
                is_new=is_new,
            )
            
            return True, fingerprint, generation_result
            
        except DuplicateContentError:
            raise
        except Exception as e:
            # Mark as failed
            await self.idempotency_repo.mark_failed(fingerprint)
            logger.error("Content processing failed", request_id=request_id, error=str(e))
            raise
    
    async def close(self) -> None:
        """Close resources."""
        await self.router.close()
        await self.llm_orchestrator.close()
        await self.idempotency_repo.close()