"""PDF content extractor using markitdown."""
import asyncio
import os

from app.config.settings import get_settings
from app.ingestion.models import ContentInput, ContentType, NormalizedContent
from app.utils.exceptions import (
    ContentTooLargeError,
    EmptyContentError,
    ExtractionError,
    IngestionError,
)
from app.utils.hashing import sha256_hash
from app.utils.logging import get_logger
from app.utils.text import is_empty_content, normalize_whitespace, sanitize_filename

logger = get_logger(__name__)


class PDFExtractor:
    """Extract content from PDF documents using markitdown."""
    
    def __init__(self):
        self.settings = get_settings()
        self._markitdown = None
    
    def _get_markitdown(self):
        """Lazy load markitdown."""
        if self._markitdown is None:
            try:
                from markitdown import MarkItDown
                self._markitdown = MarkItDown()
            except ImportError as e:
                raise ExtractionError("markitdown not available") from e
        return self._markitdown
    
    async def _read_file_header(self, file_path: str) -> bytes:
        """Read file header asynchronously."""
        def _read():
            with open(file_path, "rb") as f:
                return f.read(5)
        return await asyncio.to_thread(_read)
    
    async def extract(self, content_input: ContentInput) -> NormalizedContent:
        """Extract and normalize PDF content."""
        # content_input.raw_content should be the file path or bytes
        # For Telegram, we receive a file path from the downloader
        file_path = content_input.raw_content
        
        if not file_path or not os.path.exists(file_path):
            raise IngestionError("PDF file not found")
        
        # Check file size
        file_size = os.path.getsize(file_path)
        max_size = self.settings.max_pdf_size_mb * 1024 * 1024
        if file_size > max_size:
            raise ContentTooLargeError(
                f"PDF file too large: {file_size} bytes (max {max_size})"
            )
        
        # Verify it's a PDF
        if not file_path.lower().endswith(".pdf"):
            # Check magic bytes
            header = await self._read_file_header(file_path)
            if not header.startswith(b"%PDF"):
                raise IngestionError("File is not a valid PDF")
        
        logger.info("Processing PDF", file_path=file_path, size=file_size, user_id=content_input.user_id)
        
        # Extract with markitdown
        try:
            md = self._get_markitdown()
            result = md.convert(file_path)
            extracted_text = result.text_content
        except Exception as e:
            # Check for password protection
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                raise ExtractionError("Password-protected PDFs are not supported") from e
            raise ExtractionError(f"MarkItDown extraction failed: {e}") from e
        
        if not extracted_text or is_empty_content(extracted_text):
            raise EmptyContentError("PDF contains no extractable text content")
        
        # Normalize
        normalized = normalize_whitespace(extracted_text)
        
        if len(normalized) > self.settings.max_text_length:
            normalized = normalized[:self.settings.max_text_length]
            logger.warning("PDF content truncated", file_path=file_path, original_length=len(extracted_text))
        
        # Calculate hash
        content_hash = sha256_hash(normalized)
        
        # Source identifier for PDFs - use filename
        filename = content_input.metadata.get("filename", "document.pdf")
        source_identifier = f"pdf:{sanitize_filename(filename)}"
        
        return NormalizedContent(
            content_type=ContentType.PDF,
            source_identifier=source_identifier,
            content=normalized,
            content_hash=content_hash,
            metadata={
                **content_input.metadata,
                "filename": filename,
                "file_size": file_size,
            },
            user_id=content_input.user_id,
            message_id=content_input.message_id,
        )