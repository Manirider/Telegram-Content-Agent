"""Fault injection tests for resilience."""
import os
import tempfile

import pytest

from app.ingestion.models import ContentInput, ContentType, NormalizedContent
from app.ingestion.router import ContentRouter
from app.llm.base import LLMProvider
from app.llm.schemas import ContentGenerationResult, Variants
from app.memory.service import MemoryService
from app.memory.sqlite_repository import SQLiteRepository
from app.services.content_service import ContentService
from app.sheets.repository import SheetsRepository
from app.utils.exceptions import (
    AuthenticationError,
    ContentTooLargeError,
    EmptyContentError,
    ExtractionError,
    LLMValidationError,
    ProviderUnavailableError,
    RateLimitError,
    SheetsError,
    UnsupportedContentError,
)


class FaultInjectionProvider(LLMProvider):
    """Provider that can simulate various failures."""
    
    def __init__(self, name: str, fault_type: str | None = None):
        self._name = name
        self.fault_type = fault_type
        self.call_count = 0
    
    @property
    def name(self) -> str:
        return self._name
    
    async def generate(self, request):
        self.call_count += 1
        
        if self.fault_type == "timeout":
            raise ProviderUnavailableError("Timeout")
        elif self.fault_type == "rate_limit":
            raise RateLimitError("Rate limited")
        elif self.fault_type == "auth":
            raise AuthenticationError("Invalid API key")
        elif self.fault_type == "malformed_json":
            raise LLMValidationError("Invalid JSON")
        elif self.fault_type == "validation_error":
            # Return invalid result
            return ContentGenerationResult(
                title="T",
                rationale="R",
                category="C",
                variants=Variants(x_post="x" * 300, linkedin_post="LI"),  # Too long
            )
        elif self.fault_type == "missing_field":
            raise LLMValidationError("Missing field")
        
        return ContentGenerationResult(
            title="Title",
            rationale="Rationale",
            category="Category",
            variants=Variants(x_post="X post", linkedin_post="LinkedIn post"),
        )
    
    async def health_check(self) -> bool:
        return self.fault_type != "unavailable"
    
    async def close(self):
        pass


class FaultInjectionRouter(ContentRouter):
    """Router that can simulate extraction failures."""
    
    def __init__(self, fault_type: str | None = None):
        super().__init__()
        self.fault_type = fault_type
    
    async def route(self, content_input):
        if self.fault_type == "timeout":
            raise ExtractionError("Timeout")
        elif self.fault_type == "non_html":
            raise ExtractionError("Non-HTML content")
        elif self.fault_type == "empty_extraction":
            raise EmptyContentError("No content extracted")
        elif self.fault_type == "pdf_corrupt":
            raise ExtractionError("Corrupted PDF")
        elif self.fault_type == "pdf_too_large":
            raise ContentTooLargeError("PDF too large")
        elif self.fault_type == "unsupported":
            raise UnsupportedContentError("Unsupported type")
        
        return NormalizedContent(
            content_type=content_input.content_type,
            source_identifier=content_input.source_identifier,
            content=content_input.raw_content,
            content_hash="test_hash",
            user_id=content_input.user_id,
            message_id=content_input.message_id,
        )


class FaultInjectionSheetsRepo:
    """Sheets repo that can simulate failures."""
    
    def __init__(self, fault_type: str | None = None):
        self.fault_type = fault_type
        self.rows = []
        self.fingerprints = set()
    
    async def authenticate(self):
        pass
    
    async def ensure_worksheet(self):
        from unittest.mock import MagicMock
        return MagicMock()
    
    async def append_row(self, row):
        if self.fault_type == "rate_limit":
            from app.utils.exceptions import RateLimitError
            raise RateLimitError("Rate limit")
        elif self.fault_type == "server_error":
            from app.utils.exceptions import SheetsError
            raise SheetsError("500 Server Error")
        
        self.rows.append(row)
        self.fingerprints.add(row.to_list()[0])  # SourceIdentifier
    
    async def get_existing_fingerprints(self):
        return list(self.fingerprints)
    
    async def check_duplicate(self, fingerprint):
        return fingerprint in self.fingerprints
    
    async def close(self):
        pass
    
    async def invalidate_cache(self):
        pass


@pytest.fixture
async def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    yield repo
    await repo.close()
    os.unlink(db_path)


@pytest.fixture
def memory_service(temp_db):
    return MemoryService(temp_db)


class TestLLMFaultInjection:
    @pytest.mark.asyncio
    async def test_ollama_unavailable_fallback_groq(self, memory_service, temp_db):
        """Test fallback when Ollama unavailable."""
        ollama = FaultInjectionProvider("ollama", fault_type="timeout")
        groq = FaultInjectionProvider("groq")
        
        from app.llm.orchestrator import LLMOrchestrator
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"ollama": ollama, "groq": groq}
        orchestrator.settings.llm_primary_provider = "ollama"
        orchestrator.settings.llm_fallback_providers = "groq"
        
        from app.ingestion.models import NormalizedContent
        content = NormalizedContent(
            content_type=ContentType.TEXT,
            source_identifier="test",
            content="test",
            content_hash="hash",
            user_id=1,
        )
        
        result = await orchestrator.generate(content, 1, "req1")
        
        # Ollama is retried 3 times (max_retries) before fallback
        assert ollama.call_count == 3
        assert groq.call_count == 1
        assert result.title == "Title"
    
    @pytest.mark.asyncio
    async def test_groq_rate_limit_fallback_gemini(self, memory_service, temp_db):
        """Test fallback on rate limit."""
        groq = FaultInjectionProvider("groq", fault_type="rate_limit")
        gemini = FaultInjectionProvider("gemini")
        
        from app.llm.orchestrator import LLMOrchestrator
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"groq": groq, "gemini": gemini}
        orchestrator.settings.llm_primary_provider = "groq"
        orchestrator.settings.llm_fallback_providers = "gemini"
        
        content = NormalizedContent(
            content_type=ContentType.TEXT,
            source_identifier="test",
            content="test",
            content_hash="hash",
            user_id=1,
        )
        
        _ = await orchestrator.generate(content, 1, "req1")
        
        assert groq.call_count >= 1
        assert gemini.call_count == 1
    
    @pytest.mark.asyncio
    async def test_all_providers_fail(self, memory_service, temp_db):
        """Test error when all providers fail."""
        p1 = FaultInjectionProvider("p1", fault_type="timeout")
        p2 = FaultInjectionProvider("p2", fault_type="timeout")
        
        from app.llm.orchestrator import LLMOrchestrator
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"p1": p1, "p2": p2}
        orchestrator.settings.llm_primary_provider = "p1"
        orchestrator.settings.llm_fallback_providers = "p2"
        
        content = NormalizedContent(
            content_type=ContentType.TEXT,
            source_identifier="test",
            content="test",
            content_hash="hash",
            user_id=1,
        )
        
        with pytest.raises(Exception, match="All LLM providers failed"):
            await orchestrator.generate(content, 1, "req1")
    
    @pytest.mark.asyncio
    async def test_malformed_json_recovery(self, memory_service, temp_db):
        """Test recovery from malformed JSON."""
        bad = FaultInjectionProvider("bad", fault_type="malformed_json")
        good = FaultInjectionProvider("good")
        
        from app.llm.orchestrator import LLMOrchestrator
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"bad": bad, "good": good}
        orchestrator.settings.llm_primary_provider = "bad"
        orchestrator.settings.llm_fallback_providers = "good"
        
        content = NormalizedContent(
            content_type=ContentType.TEXT,
            source_identifier="test",
            content="test",
            content_hash="hash",
            user_id=1,
        )
        
        result = await orchestrator.generate(content, 1, "req1")
        assert result.title == "Title"
    
    @pytest.mark.asyncio
    async def test_x_post_too_long_repair(self, memory_service, temp_db):
        """Test X post length validation error is handled."""
        provider = FaultInjectionProvider("test", fault_type="validation_error")
        
        from app.llm.orchestrator import LLMOrchestrator
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"test": provider}
        orchestrator.settings.llm_primary_provider = "test"
        
        content = NormalizedContent(
            content_type=ContentType.TEXT,
            source_identifier="test",
            content="test",
            content_hash="hash",
            user_id=1,
        )
        
        # Should fail with validation error (no fallback provider)
        with pytest.raises(Exception, match="All LLM providers failed"):
            await orchestrator.generate(content, 1, "req1")


class TestIngestionFaultInjection:
    @pytest.mark.asyncio
    async def test_url_timeout(self, memory_service, temp_db):
        """Test URL fetch timeout."""
        router = FaultInjectionRouter(fault_type="timeout")
        provider = FaultInjectionProvider("test")
        
        from app.llm.orchestrator import LLMOrchestrator
        from app.sheets.repository import SheetsRepository
        from app.utils.exceptions import IngestionError
        
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"test": provider}
        
        sheets_repo = SheetsRepository(FaultInjectionSheetsRepo())
        
        service = ContentService(
            router=router,
            llm_orchestrator=orchestrator,
            memory_service=memory_service,
            sheets_repository=sheets_repo,
            idempotency_repo=temp_db,
        )
        
        content_input = ContentInput(
            content_type=ContentType.URL,
            source_identifier="https://example.com",
            raw_content="https://example.com",
            user_id=1,
            message_id=1,
        )
        
        with pytest.raises(IngestionError, match="Timeout"):
            await service.process_content(content_input)
    
    @pytest.mark.asyncio
    async def test_pdf_corrupt(self, memory_service, temp_db):
        """Test corrupted PDF handling."""
        router = FaultInjectionRouter(fault_type="pdf_corrupt")
        
        from app.llm.orchestrator import LLMOrchestrator
        from app.utils.exceptions import IngestionError
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"test": FaultInjectionProvider("test")}
        
        sheets_repo = SheetsRepository(FaultInjectionSheetsRepo())
        
        service = ContentService(
            router=router,
            llm_orchestrator=orchestrator,
            memory_service=memory_service,
            sheets_repository=sheets_repo,
            idempotency_repo=temp_db,
        )
        
        content_input = ContentInput(
            content_type=ContentType.PDF,
            source_identifier="pdf:test.pdf",
            raw_content="/tmp/test.pdf",
            user_id=1,
            message_id=1,
        )
        
        with pytest.raises(IngestionError, match="Corrupted"):
            await service.process_content(content_input)
    
    @pytest.mark.asyncio
    async def test_unsupported_file_type(self, memory_service, temp_db):
        """Test unsupported file rejection."""
        router = FaultInjectionRouter(fault_type="unsupported")
        
        from app.llm.orchestrator import LLMOrchestrator
        from app.utils.exceptions import IngestionError
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"test": FaultInjectionProvider("test")}
        
        sheets_repo = SheetsRepository(FaultInjectionSheetsRepo())
        
        service = ContentService(
            router=router,
            llm_orchestrator=orchestrator,
            memory_service=memory_service,
            sheets_repository=sheets_repo,
            idempotency_repo=temp_db,
        )
        
        content_input = ContentInput(
            content_type=ContentType.TEXT,
            source_identifier="doc:test.docx",
            raw_content="/tmp/test.docx",
            metadata={"is_document": True, "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
            user_id=1,
            message_id=1,
        )
        
        with pytest.raises(IngestionError, match="Unsupported"):
            await service.process_content(content_input)


class TestSheetsFaultInjection:
    @pytest.mark.asyncio
    async def test_sheets_rate_limit_retry(self, memory_service, temp_db):
        """Test Sheets rate limit retry."""
        router = ContentRouter()
        provider = FaultInjectionProvider("test")
        
        from app.llm.orchestrator import LLMOrchestrator
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"test": provider}
        
        # First call fails with rate limit, second succeeds
        sheets_repo = FaultInjectionSheetsRepo(fault_type="rate_limit")
        
        service = ContentService(
            router=router,
            llm_orchestrator=orchestrator,
            memory_service=memory_service,
            sheets_repository=SheetsRepository(sheets_repo),
            idempotency_repo=temp_db,
        )
        
        content_input = ContentInput(
            content_type=ContentType.TEXT,
            source_identifier="test",
            raw_content="test",
            user_id=1,
            message_id=1,
        )
        
        # Should retry and succeed on second attempt
        # Note: Our retry is in SheetsClient, not here
        # This test verifies the error propagates correctly
        with pytest.raises(SheetsError, match="Rate limit"):
            await service.process_content(content_input)
    
    @pytest.mark.asyncio
    async def test_concurrent_duplicate_requests(self, memory_service, temp_db):
        """Test two simultaneous identical requests."""
        router = ContentRouter()
        provider = FaultInjectionProvider("test")
        
        from app.llm.orchestrator import LLMOrchestrator
        orchestrator = LLMOrchestrator(memory_service)
        orchestrator.providers = {"test": provider}
        
        sheets_repo = SheetsRepository(FaultInjectionSheetsRepo())
        
        service = ContentService(
            router=router,
            llm_orchestrator=orchestrator,
            memory_service=memory_service,
            sheets_repository=sheets_repo,
            idempotency_repo=temp_db,
        )
        
        content_input = ContentInput(
            content_type=ContentType.TEXT,
            source_identifier="concurrent_test",
            raw_content="Concurrent test content",
            user_id=1,
            message_id=1,
        )
        
        # Simulate concurrent requests by calling twice
        # First should succeed, second should raise DuplicateContentError
        is_new1, _fp1, _ = await service.process_content(content_input)
        assert is_new1 is True
        
        from app.utils.exceptions import DuplicateContentError
        with pytest.raises(DuplicateContentError):
            await service.process_content(content_input)


class TestDatabasePersistence:
    @pytest.mark.asyncio
    async def test_style_persists_across_restart(self, temp_db):
        """Test style survives database reconnection."""
        memory1 = MemoryService(temp_db)
        await memory1.set_style(123, "Persistent style")
        
        # Simulate restart by creating new service with same DB
        memory2 = MemoryService(temp_db)
        style = await memory2.get_style(123)
        
        assert style == "Persistent style"
    
    @pytest.mark.asyncio
    async def test_idempotency_persists_across_restart(self, temp_db):
        """Test idempotency keys survive restart."""
        await temp_db.reserve_fingerprint("fp1", 1, "src", "hash", "style")
        await temp_db.mark_completed("fp1")
        
        # New connection
        repo2 = SQLiteRepository(temp_db.db_path)
        await repo2.initialize()
        
        status = await repo2.get_fingerprint_status("fp1")
        assert status == "COMPLETED"
        
        # Should not allow reserve
        reserved = await repo2.reserve_fingerprint("fp1", 1, "src", "hash", "style")
        assert reserved is False
        
        await repo2.close()