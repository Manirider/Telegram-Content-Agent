"""URL validation and processing utilities."""
from urllib.parse import urlparse

from app.utils.exceptions import IngestionError


def is_valid_http_url(url: str) -> bool:
    """Validate that URL uses HTTP or HTTPS scheme."""
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except (ValueError, AttributeError):
        return False


def validate_url(url: str) -> str:
    """Validate and normalize URL, raise IngestionError if invalid."""
    url = url.strip()
    if not url:
        raise IngestionError("URL cannot be empty")
    if not is_valid_http_url(url):
        raise IngestionError(f"Invalid URL: {url}. Only HTTP/HTTPS URLs are supported.")
    return url


def normalize_url(url: str) -> str:
    """Normalize URL for consistent handling."""
    parsed = urlparse(url.strip())
    # Ensure scheme is lowercase
    scheme = parsed.scheme.lower()
    # Ensure netloc is lowercase
    netloc = parsed.netloc.lower()
    # Remove default ports
    if (scheme == "http" and netloc.endswith(":80")) or \
       (scheme == "https" and netloc.endswith(":443")):
        netloc = netloc.rsplit(":", 1)[0]
    return parsed._replace(scheme=scheme, netloc=netloc).geturl()


def is_safe_url(url: str) -> bool:
    """Basic SSRF protection - reject localhost and private IPs."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Block localhost
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False
        
        # Block private IP ranges (basic check)
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            # Not an IP address, check for local hostnames
            if hostname.endswith((".local", ".internal")):
                return False
        
        return True
    except (ValueError, AttributeError):
        return False