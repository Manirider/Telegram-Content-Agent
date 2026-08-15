"""Content type router."""
from app.ingestion.models import ContentInput, ContentType, NormalizedContent
from app.ingestion.pdf_extractor import PDFExtractor
from app.ingestion.text_extractor import TextExtractor
from app.ingestion.url_extractor import URLExtractor
from app.utils.exceptions import EmptyContentError, UnsupportedContentError
from app.utils.logging import get_logger
from app.utils.text import extract_urls, is_empty_content
from app.utils.urls import is_valid_http_url

logger = get_logger(__name__)


class ContentRouter:
    """Route content to appropriate extractor based on type."""
    
    def __init__(self):
        self.text_extractor = TextExtractor()
        self.url_extractor = URLExtractor()
        self.pdf_extractor = PDFExtractor()
    
    async def route(self, content_input: ContentInput) -> NormalizedContent:
        """Route content to appropriate extractor."""
        content_type = self._detect_content_type(content_input)
        content_input.content_type = content_type
        
        logger.info("Routing content", content_type=content_type.value, user_id=content_input.user_id)
        
        if content_type == ContentType.TEXT:
            return await self.text_extractor.extract(content_input)
        elif content_type == ContentType.URL:
            return await self.url_extractor.extract(content_input)
        elif content_type == ContentType.PDF:
            return await self.pdf_extractor.extract(content_input)
        else:
            raise UnsupportedContentError(f"Unsupported content type: {content_type}")
    
    def _detect_content_type(self, content_input: ContentInput) -> ContentType:
        """Detect content type from Telegram message."""
        # Check if it's a document (PDF)
        if content_input.metadata.get("is_document"):
            mime_type = content_input.metadata.get("mime_type", "")
            filename = content_input.metadata.get("filename", "")
            if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
                return ContentType.PDF
            raise UnsupportedContentError(
                f"Unsupported document type: {mime_type or filename}. Only PDF is supported."
            )
        
        # Check if it's a URL
        raw_content = content_input.raw_content.strip()
        if is_valid_http_url(raw_content):
            # If it's a single URL, treat as URL
            urls = extract_urls(raw_content)
            if len(urls) == 1 and urls[0] == raw_content:
                return ContentType.URL
        
        # Default to text
        if is_empty_content(raw_content):
            raise EmptyContentError("Content cannot be empty")
        
        return ContentType.TEXT
    
    async def close(self) -> None:
        """Close extractors."""
        await self.url_extractor.close()