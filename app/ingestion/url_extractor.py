"""URL content extractor using trafilatura."""

import httpx
import trafilatura

from app.config.settings import get_settings
from app.ingestion.models import (
    ContentInput,
    ContentType,
    NormalizedContent,
)
from app.utils.exceptions import (
    ContentTooLargeError,
    EmptyContentError,
    ExtractionError,
    IngestionError,
)
from app.utils.hashing import sha256_hash
from app.utils.logging import get_logger
from app.utils.text import is_empty_content, normalize_whitespace
from app.utils.urls import is_safe_url, validate_url

logger = get_logger(__name__)


class URLExtractor:
    """Extract content from URLs using trafilatura."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.http_timeout_seconds),
                follow_redirects=True,
                max_redirects=self.settings.http_max_redirects,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; TelegramContentAgent/1.0; +https://github.com/telegram-content-agent)"
                },
            )
        return self.client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self.client and not self.client.is_closed:
            await self.client.aclose()
    
    async def fetch_url(self, url: str) -> tuple[str, str]:
        """
        Fetch URL content.
        Returns: (content_type, raw_html)
        """
        client = await self._get_client()
        
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.TimeoutException as e:
            raise ExtractionError(f"URL fetch timeout: {url}") from e
        except httpx.TooManyRedirects as e:
            raise ExtractionError(f"Too many redirects: {url}") from e
        except httpx.HTTPStatusError as e:
            raise ExtractionError(f"HTTP error {e.response.status_code}: {url}") from e
        except httpx.RequestError as e:
            raise ExtractionError(f"Request failed: {url}") from e
        
        content_type = response.headers.get("content-type", "").lower()
        
        # Check content type
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            logger.warning("Non-HTML content type", url=url, content_type=content_type)
            # Still try to extract, but log warning
        
        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > self.settings.max_url_content_length:
            raise ContentTooLargeError(f"URL content too large: {url}")
        
        return content_type, response.text
    
    async def extract(self, content_input: ContentInput) -> NormalizedContent:
        """Extract and normalize URL content."""
        url = content_input.raw_content.strip()
        
        # Validate URL
        url = validate_url(url)
        
        # SSRF protection
        if not is_safe_url(url):
            raise IngestionError(f"URL not allowed for security reasons: {url}")
        
        logger.info("Fetching URL", url=url, user_id=content_input.user_id)
        
        # Fetch content
        _, html = await self.fetch_url(url)
        
        # Extract with trafilatura
        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                include_formatting=True,
                deduplicate=True,
                target_language=None,
            )
        except Exception as e:
            raise ExtractionError(f"Trafilatura extraction failed: {url}") from e
        
        if not extracted or is_empty_content(extracted):
            raise EmptyContentError(f"No extractable content found at URL: {url}")
        
        # Normalize
        normalized = normalize_whitespace(extracted)
        
        if len(normalized) > self.settings.max_url_content_length:
            normalized = normalized[:self.settings.max_url_content_length]
            logger.warning("URL content truncated", url=url, original_length=len(extracted))
        
        # Calculate hash
        content_hash = sha256_hash(normalized)
        
        # Source identifier for URLs must be the original URL
        return NormalizedContent(
            content_type=ContentType.URL,
            source_identifier=url,  # Original URL as required
            content=normalized,
            content_hash=content_hash,
            metadata={
                **content_input.metadata,
                "original_url": url,
            },
            user_id=content_input.user_id,
            message_id=content_input.message_id,
        )