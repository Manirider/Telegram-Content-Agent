"""Hashing utilities for content fingerprinting."""
import hashlib


def sha256_hash(content: str) -> str:
    """Calculate SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sha256_bytes(content: bytes) -> str:
    """Calculate SHA-256 hash of bytes."""
    return hashlib.sha256(content).hexdigest()


def content_fingerprint(source_identifier: str, content_hash: str, style_hash: str) -> str:
    """Generate idempotency fingerprint combining source, content, and style."""
    combined = f"{source_identifier}|{content_hash}|{style_hash}"
    return sha256_hash(combined)


def style_hash(style_prompt: str | None) -> str:
    """Generate hash of style prompt. Empty style returns empty hash."""
    if not style_prompt or not style_prompt.strip():
        return "no-style"
    return sha256_hash(style_prompt.strip())


def normalize_url_for_hash(url: str) -> str:
    """Normalize URL for internal deduplication while preserving original for SourceIdentifier."""
    from urllib.parse import parse_qs, urlencode, urlparse
    
    parsed = urlparse(url.strip())
    # Remove fragment
    parsed = parsed._replace(fragment="")
    # Sort query parameters
    if parsed.query:
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        sorted_query = urlencode(sorted(query_params.items()), doseq=True)
        parsed = parsed._replace(query=sorted_query)
    # Normalize scheme and netloc to lowercase
    parsed = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    # Remove default ports
    if (parsed.scheme == "http" and parsed.netloc.endswith(":80")) or \
       (parsed.scheme == "https" and parsed.netloc.endswith(":443")):
        parsed = parsed._replace(netloc=parsed.netloc.rsplit(":", 1)[0])
    # Remove trailing slash from path if it's just root
    if parsed.path == "/":
        parsed = parsed._replace(path="")
    return parsed.geturl()