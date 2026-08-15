"""Text processing utilities."""
import re


def normalize_whitespace(text: str) -> str:
    """Normalize excessive whitespace while preserving paragraph structure."""
    # Replace multiple spaces/tabs with single space
    text = re.sub(r'[ \t]+', ' ', text)
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Strip leading/trailing whitespace
    return text.strip()


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max length with suffix."""
    if len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return suffix[:max_length]
    return text[:max_length - len(suffix)].rstrip() + suffix


def is_empty_content(text: str) -> bool:
    """Check if content is effectively empty."""
    return not text or not text.strip()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    # Remove path components
    filename = filename.split("/")[-1].split("\\")[-1]
    # Remove dangerous characters
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    # Limit length
    return filename[:255]


def extract_urls(text: str) -> list[str]:
    """Extract URLs from text."""
    url_pattern = re.compile(
        r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[^\s]*)?'
    )
    return url_pattern.findall(text)


def count_characters(text: str) -> int:
    """Count characters in text (for X post validation)."""
    return len(text)


def ensure_max_length(text: str, max_length: int) -> str:
    """Ensure text does not exceed max length, truncating if necessary."""
    if len(text) <= max_length:
        return text
    # Try to truncate at word boundary
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.8:  # If we can find a space in the last 20%
        return truncated[:last_space].rstrip() + "..."
    return truncated[:max_length - 3] + "..."