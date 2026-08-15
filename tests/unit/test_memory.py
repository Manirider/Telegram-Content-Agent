"""Unit tests for memory service and idempotency."""
import os
import tempfile

import pytest

from app.memory.service import MemoryService
from app.memory.sqlite_repository import SQLiteRepository
from app.utils.exceptions import ValidationError
from app.utils.hashing import style_hash


@pytest.fixture
async def db_repo():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    
    yield repo
    
    await repo.close()
    os.unlink(db_path)


@pytest.fixture
async def memory_service(db_repo):
    return MemoryService(db_repo)


class TestSQLiteRepository:
    async def test_get_style_nonexistent(self, db_repo):
        result = await db_repo.get_style(12345)
        assert result is None
    
    async def test_set_and_get_style(self, db_repo):
        style = await db_repo.set_style(12345, "Test style")
        assert style.user_id == 12345
        assert style.style_prompt == "Test style"
        
        retrieved = await db_repo.get_style(12345)
        assert retrieved.style_prompt == "Test style"
    
    async def test_update_style(self, db_repo):
        await db_repo.set_style(12345, "Old style")
        updated = await db_repo.set_style(12345, "New style")
        
        assert updated.style_prompt == "New style"
        retrieved = await db_repo.get_style(12345)
        assert retrieved.style_prompt == "New style"
    
    async def test_clear_style(self, db_repo):
        await db_repo.set_style(12345, "Style to clear")
        cleared = await db_repo.clear_style(12345)
        assert cleared is True
        
        retrieved = await db_repo.get_style(12345)
        assert retrieved is None
        
        # Clearing again returns False
        cleared = await db_repo.clear_style(12345)
        assert cleared is False


class TestMemoryService:
    async def test_get_style_nonexistent(self, memory_service):
        result = await memory_service.get_style(99999)
        assert result is None
    
    async def test_set_style(self, memory_service):
        style = await memory_service.set_style(11111, "My custom style")
        assert style == "My custom style"
        
        retrieved = await memory_service.get_style(11111)
        assert retrieved == "My custom style"
    
    async def test_set_style_strips_whitespace(self, memory_service):
        style = await memory_service.set_style(22222, "  Trimmed style  ")
        assert style == "Trimmed style"
    
    async def test_set_style_empty_raises(self, memory_service):
        with pytest.raises(ValidationError, match="empty"):
            await memory_service.set_style(33333, "")
    
    async def test_set_style_too_long_raises(self, memory_service):
        long_style = "x" * 2001
        with pytest.raises(ValidationError, match="too long"):
            await memory_service.set_style(44444, long_style)
    
    async def test_clear_style(self, memory_service):
        await memory_service.set_style(55555, "To be cleared")
        cleared = await memory_service.clear_style(55555)
        assert cleared is True
        
        style = await memory_service.get_style(55555)
        assert style is None
    
    async def test_style_hash(self, memory_service):
        # No style
        h1 = await memory_service.get_style_hash(99999)
        assert h1 == "no-style"
        
        # With style
        await memory_service.set_style(66666, "Test style")
        h2 = await memory_service.get_style_hash(66666)
        assert h2 == style_hash("Test style")
        assert len(h2) == 64


class TestIdempotencyRepository:
    async def test_reserve_new_fingerprint(self, db_repo):
        reserved = await db_repo.reserve_fingerprint(
            fingerprint="fp1",
            user_id=1,
            source_identifier="src1",
            content_hash="ch1",
            style_hash="sh1",
        )
        assert reserved is True
    
    async def test_reserve_duplicate_completed(self, db_repo):
        # First reserve and complete
        await db_repo.reserve_fingerprint("fp1", 1, "src1", "ch1", "sh1")
        await db_repo.mark_completed("fp1")
        
        # Try to reserve again
        reserved = await db_repo.reserve_fingerprint("fp1", 1, "src1", "ch1", "sh1")
        assert reserved is False
    
    async def test_reserve_stale_processing_allows_retry(self, db_repo):
        # Reserve but don't complete (simulating crash)
        await db_repo.reserve_fingerprint("fp1", 1, "src1", "ch1", "sh1")
        
        # Should allow retry (updates timestamp)
        reserved = await db_repo.reserve_fingerprint("fp1", 1, "src1", "ch1", "sh1")
        assert reserved is True
    
    async def test_reserve_failed_allows_retry(self, db_repo):
        await db_repo.reserve_fingerprint("fp1", 1, "src1", "ch1", "sh1")
        await db_repo.mark_failed("fp1")
        
        reserved = await db_repo.reserve_fingerprint("fp1", 1, "src1", "ch1", "sh1")
        assert reserved is True
    
    async def test_mark_completed_and_failed(self, db_repo):
        await db_repo.reserve_fingerprint("fp1", 1, "src1", "ch1", "sh1")
        await db_repo.mark_completed("fp1")
        
        status = await db_repo.get_fingerprint_status("fp1")
        assert status == "COMPLETED"
        
        # New fingerprint for failed test
        await db_repo.reserve_fingerprint("fp2", 1, "src1", "ch1", "sh1")
        await db_repo.mark_failed("fp2")
        
        status = await db_repo.get_fingerprint_status("fp2")
        assert status == "FAILED"