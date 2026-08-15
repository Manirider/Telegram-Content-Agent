"""SQLite repository for style memory and idempotency."""
from datetime import datetime, timezone

import aiosqlite

from app.memory.models import UserStyle
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SQLiteRepository:
    """SQLite repository for persistent storage."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._pool: aiosqlite.Connection | None = None
    
    async def initialize(self) -> None:
        """Initialize database schema."""
        import os
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        async with aiosqlite.connect(self.db_path) as db:
            # Style memory table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS style_memory (
                    user_id INTEGER PRIMARY KEY,
                    style_prompt TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Idempotency tracking table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    fingerprint TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    source_identifier TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    style_hash TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Index for cleanup queries
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_idempotency_user 
                ON idempotency_keys(user_id)
            """)
            
            await db.commit()
        
        logger.info("Database initialized", db_path=self.db_path)
    
    async def close(self) -> None:
        """Close database connections."""
        # aiosqlite connections are per-operation, nothing to close explicitly
    
    # Style Memory Operations
    
    async def get_style(self, user_id: int) -> UserStyle | None:
        """Get user's style prompt."""
        async with aiosqlite.connect(self.db_path) as db, db.execute(
            "SELECT user_id, style_prompt, created_at, updated_at FROM style_memory WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return UserStyle.from_row(row)
        return None
    
    async def set_style(self, user_id: int, style_prompt: str) -> UserStyle:
        """Set or update user's style prompt."""
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO style_memory (user_id, style_prompt, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    style_prompt = excluded.style_prompt,
                    updated_at = excluded.updated_at
            """, (user_id, style_prompt, now, now))
            await db.commit()
        
        logger.info("Style updated", user_id=user_id, style_length=len(style_prompt))
        return UserStyle(user_id=user_id, style_prompt=style_prompt, created_at=now, updated_at=now)
    
    async def clear_style(self, user_id: int) -> bool:
        """Clear user's style prompt."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM style_memory WHERE user_id = ?", (user_id,))
            await db.commit()
            return cursor.rowcount > 0
    
    # Idempotency Operations
    
    async def reserve_fingerprint(
        self,
        fingerprint: str,
        user_id: int,
        source_identifier: str,
        content_hash: str,
        style_hash: str,
    ) -> bool:
        """
        Reserve a fingerprint for processing.
        Returns True if reserved (not previously seen), False if already exists.
        """
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO idempotency_keys 
                    (fingerprint, status, user_id, source_identifier, content_hash, style_hash, created_at, updated_at)
                    VALUES (?, 'PROCESSING', ?, ?, ?, ?, ?, ?)
                """, (fingerprint, user_id, source_identifier, content_hash, style_hash, now, now))
                await db.commit()
                logger.info("Fingerprint reserved", fingerprint=fingerprint[:16], user_id=user_id)
                return True
            except aiosqlite.IntegrityError:
                # Fingerprint already exists
                async with db.execute(
                    "SELECT status FROM idempotency_keys WHERE fingerprint = ?", (fingerprint,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0] == "COMPLETED":
                        logger.info("Duplicate fingerprint (completed)", fingerprint=fingerprint[:16])
                        return False
                    elif row and row[0] == "PROCESSING":
                        # Stale processing - could be a crash recovery scenario
                        # We'll allow retry by updating timestamp
                        await db.execute(
                            "UPDATE idempotency_keys SET updated_at = ? WHERE fingerprint = ?",
                            (now, fingerprint)
                        )
                        await db.commit()
                        logger.warning("Stale PROCESSING fingerprint, allowing retry", fingerprint=fingerprint[:16])
                        return True
                    else:
                        # FAILED or other - allow retry
                        await db.execute(
                            "UPDATE idempotency_keys SET status = 'PROCESSING', updated_at = ? WHERE fingerprint = ?",
                            (now, fingerprint)
                        )
                        await db.commit()
                        logger.info("Retrying failed fingerprint", fingerprint=fingerprint[:16])
                        return True
    
    async def mark_completed(self, fingerprint: str) -> None:
        """Mark fingerprint as completed."""
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE idempotency_keys SET status = 'COMPLETED', updated_at = ? WHERE fingerprint = ?",
                (now, fingerprint)
            )
            await db.commit()
        logger.info("Fingerprint marked completed", fingerprint=fingerprint[:16])
    
    async def mark_failed(self, fingerprint: str) -> None:
        """Mark fingerprint as failed."""
        now = datetime.now(timezone.utc)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE idempotency_keys SET status = 'FAILED', updated_at = ? WHERE fingerprint = ?",
                (now, fingerprint)
            )
            await db.commit()
        logger.info("Fingerprint marked failed", fingerprint=fingerprint[:16])
    
    async def get_fingerprint_status(self, fingerprint: str) -> str | None:
        """Get status of a fingerprint."""
        async with aiosqlite.connect(self.db_path) as db, db.execute(
            "SELECT status FROM idempotency_keys WHERE fingerprint = ?", (fingerprint,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def cleanup_stale_processing(self, max_age_hours: int = 24) -> int:
        """Clean up stale PROCESSING records older than max_age_hours."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM idempotency_keys WHERE status = 'PROCESSING' AND updated_at < ?",
                (cutoff,)
            )
            await db.commit()
            return cursor.rowcount