"""Integration tests with fake providers."""
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from app.ingestion.models import ContentInput, ContentType, NormalizedContent
from app.llm.base import LLMProvider
from app.llm.orchestrator import LLMOrchestrator
from app.llm.schemas import ContentGenerationResult, Variants
from app.memory.service import MemoryService
from app.memory.sqlite_repository import SQLiteRepository
from app.services.content_service import ContentService
from app.sheets.repository import SheetsRepository


class FakeLLMProvider(LLMProvider):
    """Fake LLM provider for testing."""
    
    def __init__(self, name: str, should_fail: bool = False, response: ContentGenerationResult = None):
        self._name = name
        self.should_fail = should_fail
        self._response = response or ContentGenerationResult(
            title="Test Title",
            rationale="Test rationale",
            category="Technology",
            variants=Variants(x_post="Test X post", linkedin_post="Test LinkedIn post"),
        )
        self.call_count = 0
    
    @property
    def name(self) -> str:
        return self._name
    
    async def generate(self, request) -> ContentGenerationResult:
        self.call_count += 1
        if self.should_fail:
            from app.utils.exceptions import ProviderUnavailableError
            raise ProviderUnavailableError(f"{self._name} failed")
        return self._response
    
    async def health_check(self) -> bool:
        return not self.should_fail
    
    async def close(self) -> None:
        pass


class FakeSheetsClient:
    """Fake Google Sheets client for testing."""
    
    def __init__(self):
        self.rows = []
        self.fingerprints = set()
        self.should_fail = False
    
    async def authenticate(self):
        pass
    
    async def ensure_worksheet(self):
        return MagicMock()
    
    async def append_row(self, row):
        if self.should_fail:
            from app.utils.exceptions import SheetsError
            raise SheetsError("Sheets failed")
        self.rows.append(row)
        self.fingerprints.add(row.to_list()[0])  # SourceIdentifier
    
    async def get_existing_fingerprints(self):
        return list(self.fingerprints)
    
    async def check_duplicate(self, fingerprint):
        return fingerprint in self.fingerprints
    
    async def close(self):
        pass


class FakeContentRouter:
    """Fake content router for testing."""
    
    def __init__(self):
        self.should_fail = False
        self.content_type = ContentType.TEXT
    
    async def route(self, content_input):
        if self.should_fail:
            from app.utils.exceptions import IngestionError
            raise IngestionError("Routing failed")
        
        return NormalizedContent(
            content_type=self.content_type,
            source_identifier=content_input.source_identifier,
            content=content_input.raw_content,
            content_hash="test_hash",
            user_id=content_input.user_id,
            message_id=content_input.message_id,
        )
    
    async def close(self):
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


@pytest.fixture
def fake_sheets_client():
    return FakeSheetsClient()


@pytest.fixture
def fake_sheets_repo(fake_sheets_client):
    return SheetsRepository(fake_sheets_client)


@pytest.fixture
def fake_router():
    return FakeContentRouter()


@pytest.fixture
def fake_llm_provider():
    return FakeLLMProvider("fake")


@pytest.fixture
def llm_orchestrator(memory_service, fake_llm_provider):
    orchestrator = LLMOrchestrator(memory_service)
    orchestrator.providers = {"fake": fake_llm_provider}
    orchestrator.settings.llm_primary_provider = "fake"
    orchestrator.settings.llm_fallback_providers = ""
    return orchestrator


@pytest.fixture
def content_service(fake_router, llm_orchestrator, memory_service, fake_sheets_repo, temp_db):
    return ContentService(
        router=fake_router,
        llm_orchestrator=llm_orchestrator,
        memory_service=memory_service,
        sheets_repository=fake_sheets_repo,
        idempotency_repo=temp_db,
    )


class TestContentServiceIntegration:
    @pytest.mark.asyncio
    async def test_process_text_content(self, content_service, memory_service):
        """Test full text processing pipeline."""
        content_input = ContentInput(
            content_type=ContentType.TEXT,
            source_identifier="text:123",
            raw_content="This is test content for processing",
            user_id=12345,
            message_id=1,
        )
        
        is_new, fingerprint, result = await content_service.process_content(content_input)
        
        assert is_new is True
        assert result is not None
        assert result.title == "Test Title"
        assert fingerprint is not None
    
    @pytest.mark.asyncio
    async def test_duplicate_rejection(self, content_service, memory_service):
        """Test duplicate content with same style is rejected."""
        content_input = ContentInput(
            content_type=ContentType.TEXT,
            source_identifier="text:456",
            raw_content="Duplicate test content",
            user_id=12345,
            message_id=2,
        )
        
        # First submission
        is_new1, _fp1, _result1 = await content_service.process_content(content_input)
        assert is_new1 is True
        
        # Second submission (same content, same style) - raises DuplicateContentError
        from app.utils.exceptions import DuplicateContentError
        with pytest.raises(DuplicateContentError):
            await content_service.process_content(content_input)
    
    @pytest.mark.asyncio
    async def test_style_change_creates_new_row(self, content_service, memory_service):
        """Test same content with different style creates new row."""
        content_input = ContentInput(
            content_type=ContentType.TEXT,
            source_identifier="text:789",
            raw_content="Style change test",
            user_id=12345,
            message_id=3,
        )
        
        # First with default style
        is_new1, fp1, _ = await content_service.process_content(content_input)
        assert is_new1 is True
        
        # Change style
        await memory_service.set_style(12345, "New style: haiku only")
        
        # Same content, new style
        is_new2, fp2, _ = await content_service.process_content(content_input)
        assert is_new2 is True
        assert fp1 != fp2
    
    @pytest.mark.asyncio
    async def test_llm_fallback(self, content_service, memory_service, llm_orchestrator):
        """Test fallback to secondary provider when primary fails."""
        # Make primary fail
        primary = FakeLLMProvider("primary", should_fail=True)
        fallback = FakeLLMProvider("fallback")
        
        llm_orchestrator.providers = {"primary": primary, "fallback": fallback}
        llm_orchestrator.settings.llm_primary_provider = "primary"
        llm_orchestrator.settings.llm_fallback_providers = "fallback"
        
        content_input = ContentInput(
            content_type=ContentType.TEXT,
            source_identifier="text:fallback",
            raw_content="Fallback test",
            user_id=12345,
            message_id=4,
        )
        
        is_new, _fp, result = await content_service.process_content(content_input)
        
        assert is_new is True
        assert result is not None
        assert primary.call_count > 0  # Primary was tried
        assert fallback.call_count > 0  # Fallback was used
    
    @pytest.mark.asyncio
    async def test_all_providers_fail(self, content_service, llm_orchestrator):
        """Test error when all providers fail."""
        fail_provider = FakeLLMProvider("fail", should_fail=True)
        llm_orchestrator.providers = {"fail": fail_provider}
        llm_orchestrator.settings.llm_primary_provider = "fail"
        
        content_input = ContentInput(
            content_type=ContentType.TEXT,
            source_identifier="text:fail",
            raw_content="Fail test",
            user_id=12345,
            message_id=5,
        )
        
        with pytest.raises(Exception, match="All LLM providers failed"):
            await content_service.process_content(content_input)