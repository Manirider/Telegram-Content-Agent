"""Content ingestion models."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ContentType(str, Enum):
    """Supported content types."""
    TEXT = "text"
    URL = "url"
    PDF = "pdf"


@dataclass
class ContentInput:
    """Raw content input from Telegram."""
    content_type: ContentType
    source_identifier: str
    raw_content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    user_id: int = 0
    message_id: int = 0


@dataclass
class NormalizedContent:
    """Normalized content ready for LLM processing."""
    content_type: ContentType
    source_identifier: str
    content: str
    content_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)
    user_id: int = 0
    message_id: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ExtractedContent:
    """Content extracted from URL or PDF."""
    content: str
    title: str | None = None
    author: str | None = None
    publish_date: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)