"""Text content extractor."""
from app.config.settings import get_settings
from app.ingestion.models import ContentInput, ContentType, NormalizedContent
from app.utils.exceptions import ContentTooLargeError, EmptyContentError
from app.utils.hashing import sha256_hash
from app.utils.logging import get_logger
from app.utils.text import is_empty_content, normalize_whitespace

logger = get_logger(__name__)


class TextExtractor:
    """Extract and normalize plain text content."""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def extract(self, content_input: ContentInput) -> NormalizedContent:
        """Extract and normalize text content."""
        raw_text = content_input.raw_content
        
        if is_empty_content(raw_text):
            raise EmptyContentError("Text content cannot be empty")
        
        if len(raw_text) > self.settings.max_text_length:
            raise ContentTooLargeError(
                f"Text content exceeds maximum length of {self.settings.max_text_length} characters"
            )
        
        # Normalize whitespace
        normalized = normalize_whitespace(raw_text)
        
        if is_empty_content(normalized):
            raise EmptyContentError("Text content is empty after normalization")
        
        # Calculate hash
        content_hash = sha256_hash(normalized)
        
        return NormalizedContent(
            content_type=ContentType.TEXT,
            source_identifier=content_input.source_identifier,
            content=normalized,
            content_hash=content_hash,
            metadata=content_input.metadata,
            user_id=content_input.user_id,
            message_id=content_input.message_id,
        )