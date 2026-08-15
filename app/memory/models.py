"""Database models for memory layer."""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class UserStyle:
    """User style memory record."""
    user_id: int
    style_prompt: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Sequence[Any]) -> "UserStyle":
        """Create from database row."""
        return cls(
            user_id=row[0],
            style_prompt=row[1],
            created_at=datetime.fromisoformat(row[2]) if isinstance(row[2], str) else row[2],
            updated_at=datetime.fromisoformat(row[3]) if isinstance(row[3], str) else row[3],
        )


@dataclass
class IdempotencyRecord:
    """Idempotency tracking record."""
    fingerprint: str
    status: str  # PROCESSING, COMPLETED, FAILED
    user_id: int
    source_identifier: str
    content_hash: str
    style_hash: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Sequence[Any]) -> "IdempotencyRecord":
        """Create from database row."""
        return cls(
            fingerprint=row[0],
            status=row[1],
            user_id=row[2],
            source_identifier=row[3],
            content_hash=row[4],
            style_hash=row[5],
            created_at=datetime.fromisoformat(row[6]) if isinstance(row[6], str) else row[6],
            updated_at=datetime.fromisoformat(row[7]) if isinstance(row[7], str) else row[7],
        )