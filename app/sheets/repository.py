"""Google Sheets repository with idempotency."""

from app.config.settings import get_settings
from app.ingestion.models import NormalizedContent
from app.llm.schemas import ContentGenerationResult
from app.sheets.client import SheetsClient
from app.sheets.schemas import (
    CONTENT_TYPE_VALUES,
    SheetsRow,
)
from app.utils.exceptions import SheetsError, ValidationError
from app.utils.hashing import content_fingerprint
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SheetsRepository:
    """Repository for Google Sheets operations with idempotency."""
    
    def __init__(self, client: SheetsClient):
        self.client = client
        self.settings = get_settings()
        self._fingerprint_cache: set | None = None
        self._cache_valid = False
    
    async def initialize(self) -> None:
        """Initialize repository."""
        await self.client.ensure_worksheet()
        await self._refresh_fingerprint_cache()
    
    async def _refresh_fingerprint_cache(self) -> None:
        """Refresh local fingerprint cache."""
        try:
            existing = await self.client.get_existing_fingerprints()
            self._fingerprint_cache = set(existing)
            self._cache_valid = True
            logger.debug("Fingerprint cache refreshed", count=len(self._fingerprint_cache))
        except (OSError, RuntimeError, SheetsError) as e:
            logger.warning("Failed to refresh fingerprint cache", error=str(e))
            self._fingerprint_cache = set()
            self._cache_valid = False
    
    def _validate_content_type(self, content_type: str) -> None:
        """Validate content type is one of allowed values."""
        if content_type not in CONTENT_TYPE_VALUES:
            raise ValidationError(f"Invalid ContentType: {content_type}. Must be one of {CONTENT_TYPE_VALUES}")
    
    def _validate_generation_result(self, result: ContentGenerationResult) -> None:
        """Validate generation result before insertion."""
        if not result.title.strip():
            raise ValidationError("Title cannot be empty")
        if not result.rationale.strip():
            raise ValidationError("Rationale cannot be empty")
        if not result.category.strip():
            raise ValidationError("Category cannot be empty")
        if not result.variants.x_post.strip():
            raise ValidationError("X variant cannot be empty")
        if not result.variants.linkedin_post.strip():
            raise ValidationError("LinkedIn variant cannot be empty")
        if len(result.variants.x_post) > 280:
            raise ValidationError(f"X variant exceeds 280 characters: {len(result.variants.x_post)}")
        if result.variants.x_post.strip() == result.variants.linkedin_post.strip():
            raise ValidationError("X variant and LinkedIn variant must be different")
    
    def _build_row(
        self,
        content: NormalizedContent,
        result: ContentGenerationResult,
        style_hash: str,
    ) -> tuple[SheetsRow, str]:
        """Build SheetsRow and calculate fingerprint."""
        self._validate_content_type(content.content_type.value)
        self._validate_generation_result(result)
        
        row = SheetsRow.from_generation(
            source_identifier=content.source_identifier,
            content_type=content.content_type.value,
            title=result.title.strip(),
            rationale=result.rationale.strip(),
            category=result.category.strip(),
            x_variant=result.variants.x_post.strip(),
            linkedin_variant=result.variants.linkedin_post.strip(),
        )
        
        fingerprint = content_fingerprint(
            content.source_identifier,
            content.content_hash,
            style_hash,
        )
        
        return row, fingerprint
    
    async def save(
        self,
        content: NormalizedContent,
        result: ContentGenerationResult,
        style_hash: str,
    ) -> tuple[bool, str]:
        """
        Save content to Google Sheets with idempotency.
        
        Returns: (is_new_row, fingerprint)
        - is_new_row: True if row was inserted, False if duplicate
        - fingerprint: The idempotency fingerprint
        """
        row, fingerprint = self._build_row(content, result, style_hash)
        
        # Check cache first
        if self._cache_valid and self._fingerprint_cache and fingerprint in self._fingerprint_cache:
            logger.info("Duplicate detected (cache)", fingerprint=fingerprint[:16])
            return False, fingerprint
        
        # Verify with Sheets (source of truth)
        try:
            is_duplicate = await self.client.check_duplicate(fingerprint)
            if is_duplicate:
                # Update cache
                if self._cache_valid and self._fingerprint_cache:
                    self._fingerprint_cache.add(fingerprint)
                logger.info("Duplicate detected (Sheets)", fingerprint=fingerprint[:16])
                return False, fingerprint
        except (OSError, RuntimeError, SheetsError) as e:
            logger.warning("Duplicate check failed, proceeding with insert", error=str(e))
        
        # Insert new row
        try:
            await self.client.append_row(row)
            
            # Update cache
            if self._cache_valid and self._fingerprint_cache:
                self._fingerprint_cache.add(fingerprint)
            
            logger.info("Row inserted", fingerprint=fingerprint[:16], source=content.source_identifier[:50])
            return True, fingerprint
            
        except Exception as e:
            # Invalidate cache on error
            self._cache_valid = False
            raise SheetsError(f"Failed to save to Sheets: {e}") from e
    
    async def invalidate_cache(self) -> None:
        """Invalidate fingerprint cache."""
        self._cache_valid = False
        self._fingerprint_cache = None