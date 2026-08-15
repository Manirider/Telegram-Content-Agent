# Developer Guide

Complete guide for local development, debugging, and extending the Telegram Content Agent.

## Quick Start

```bash
# 1. Clone & setup
git clone <repo>
cd telegram-content-agent

# 2. Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pre-commit install

# 3. Configuration
cp .env.example .env
# Edit .env with your tokens (see SETUP.md)

# 4. Run tests
pytest

# 5. Run application
python -m app.main
```

## Development Workflow

### Code Changes

1. **Create feature branch**: `git checkout -b feature/your-feature`
2. **Make changes** following coding standards
3. **Run tests**: `pytest`
4. **Check quality**: `ruff check app/ tests/ && mypy app/`
5. **Commit**: `git commit -m "feat: your feature"`
6. **Push & PR**: `git push origin feature/your-feature`

### Debugging

#### VS Code Launch Config

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug App",
      "type": "python",
      "request": "launch",
      "module": "app.main",
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal",
      "justMyCode": true
    },
    {
      "name": "Debug Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "--tb=short"],
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    },
    {
      "name": "Debug Single Test",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v", "--tb=long", "${file}"],
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    }
  ]
}
```

#### Remote Debugging (Docker)

```yaml
# docker-compose.override.yml (for debugging)
services:
  app:
    build:
      target: builder  # Use builder stage with debug tools
    command: python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m app.main
    ports:
      - "5678:5678"  # Debug port
    volumes:
      - ./app:/app/app  # Hot reload
```

```json
// VS Code attach config
{
  "name": "Attach to Docker",
  "type": "python",
  "request": "attach",
  "connect": {"host": "localhost", "port": 5678},
  "pathMappings": [{"localRoot": "${workspaceFolder}/app", "remoteRoot": "/app/app"}]
}
```

### Hot Reloading

```bash
# Install watchdog for auto-reload
pip install watchdog

# Run with auto-reload
watchmedo auto-restart --directory=./app --pattern=*.py --recursive -- python -m app.main
```

## Project Deep Dive

### Adding a New LLM Provider

#### 1. Implement the Protocol

```python
# app/llm/new_provider.py
from app.llm.base import LLMProvider
from app.llm.schemas import ContentGenerationResult, LLMRequest
from app.utils.exceptions import ProviderUnavailableError

class NewProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "newprovider"
    
    async def generate(self, request: LLMRequest) -> ContentGenerationResult:
        # Your implementation
        ...
    
    async def health_check(self) -> bool:
        # Check connectivity
        ...
    
    async def close(self) -> None:
        # Cleanup
        ...
```

#### 2. Register in Orchestrator

```python
# app/llm/orchestrator.py
def _initialize_providers(self) -> None:
    # ... existing providers ...
    
    # New provider (if configured)
    if self.settings.newprovider_api_key:
        self.providers["newprovider"] = NewProvider()
```

#### 3. Add Configuration

```python
# app/config/settings.py
class Settings(BaseSettings):
    # ... existing ...
    newprovider_api_key: str | None = Field(default=None)
    newprovider_model: str = Field(default="default-model")
    newprovider_timeout_seconds: int = Field(default=60)
```

#### 4. Update .env.example

```env
# New Provider
NEWPROVIDER_API_KEY=
NEWPROVIDER_MODEL=default-model
NEWPROVIDER_TIMEOUT_SECONDS=60
```

#### 5. Add Tests

```python
# tests/unit/test_new_provider.py
import pytest
from app.llm.new_provider import NewProvider

@pytest.mark.asyncio
async def test_new_provider_generate():
    provider = NewProvider(api_key="test", model="test")
    # Mock HTTP calls, test generate()
    ...
```

### Adding a New Content Type

#### 1. Update Models

```python
# app/ingestion/models.py
class ContentType(str, Enum):
    TEXT = "text"
    URL = "url"
    PDF = "pdf"
    DOCX = "docx"  # New type
```

#### 2. Create Extractor

```python
# app/ingestion/docx_extractor.py
from app.ingestion.models import ContentInput, ContentType, NormalizedContent

class DOCXExtractor:
    async def extract(self, content_input: ContentInput) -> NormalizedContent:
        # Use python-docx or similar
        # Return NormalizedContent
        ...
```

#### 3. Register in Router

```python
# app/ingestion/router.py
def _detect_content_type(self, content_input: ContentInput) -> ContentType:
    # ... existing logic ...
    
    # Check for DOCX
    if content_input.metadata.get("is_document"):
        filename = content_input.metadata.get("filename", "")
        if filename.lower().endswith(".docx"):
            return ContentType.DOCX
```

```python
# app/ingestion/router.py
async def route(self, content_input: ContentInput) -> NormalizedContent:
    # ... existing ...
    
    if content_type == ContentType.DOCX:
        return await self.docx_extractor.extract(content_input)
```

#### 4. Update Sheets Schema

```python
# app/sheets/schemas.py
CONTENT_TYPE_VALUES = {"text", "url", "pdf", "docx"}
```

#### 5. Add Tests

```python
# tests/integration/test_docx_pipeline.py
@pytest.mark.asyncio
async def test_docx_processing(content_service):
    content_input = ContentInput(
        content_type=ContentType.DOCX,
        source_identifier="docx:test.docx",
        raw_content="/path/to/test.docx",
        metadata={"is_document": True, "filename": "test.docx"},
        user_id=1,
    )
    is_new, fp, result = await content_service.process_content(content_input)
    assert is_new is True
    assert result.content_type == ContentType.DOCX
```

### Customizing Prompts

#### Modify System Prompt

```python
# app/llm/prompts.py
SYSTEM_PROMPT = """You are an expert content strategist...

NEW REQUIREMENT: Always include a hashtag in X posts.
"""
```

#### Add Style-Specific Instructions

```python
# app/llm/prompts.py
def build_user_prompt(content: NormalizedContent, style_prompt: str | None) -> str:
    parts = []
    
    if style_prompt:
        parts.append(f"USER STYLE PREFERENCE: {style_prompt}")
        parts.append("")
    
    # Add content-type specific instructions
    if content.content_type == ContentType.PDF:
        parts.append("NOTE: This content was extracted from a PDF document.")
    
    parts.extend([...])
    return "\n".join(parts)
```

### Extending Google Sheets Output

#### Add Custom Columns

```python
# app/sheets/schemas.py
REQUIRED_HEADERS = [
    "SourceIdentifier",
    "SubmissionTimestamp",
    "ContentType",
    "LLMTitle",
    "Rationale",
    "Category",
    "X_Variant",
    "LinkedIn_Variant",
    "CustomField",  # New column
]

@dataclass
class SheetsRow:
    # ... existing fields ...
    custom_field: str = ""
    
    def to_list(self) -> list:
        return [
            # ... existing ...
            self.custom_field,
        ]
```

#### Populate in Repository

```python
# app/sheets/repository.py
def _build_row(self, content, result, style_hash):
    # ... existing ...
    
    row = SheetsRow.from_generation(
        # ... existing ...
        custom_field="your_value",
    )
```

## Testing Strategies

### Mocking External Services

```python
# tests/conftest.py
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_telegram():
    mock = AsyncMock()
    mock.send_message = AsyncMock()
    return mock

@pytest.fixture
def mock_sheets_client():
    client = MagicMock()
    client.authenticate = AsyncMock()
    client.ensure_worksheet = AsyncMock(return_value=MagicMock())
    client.append_row = AsyncMock()
    client.get_existing_fingerprints = AsyncMock(return_value=[])
    client.check_duplicate = AsyncMock(return_value=False)
    return client
```

### Testing with Real Services (Integration)

```bash
# Use test credentials for real API testing
export TELEGRAM_BOT_TOKEN=test_token
export GOOGLE_SHEETS_CREDENTIALS_B64=test_creds
export GOOGLE_SHEETS_SPREADSHEET_ID=test_sheet
export GROQ_API_KEY=test_groq_key

# Run integration tests
pytest tests/integration/ -v -k "not fault"
```

### Property-Based Testing

```python
# tests/unit/test_hashing_properties.py
from hypothesis import given, strategies as st
from app.utils.hashing import content_fingerprint, style_hash

@given(
    source=st.text(min_size=1),
    content_hash=st.text(min_size=64, max_size=64),
    style=st.text()
)
def test_fingerprint_deterministic(source, content_hash, style):
    fp1 = content_fingerprint(source, content_hash, style_hash(style))
    fp2 = content_fingerprint(source, content_hash, style_hash(style))
    assert fp1 == fp2

@given(
    source1=st.text(min_size=1),
    source2=st.text(min_size=1),
    content_hash=st.text(min_size=64, max_size=64),
    style=st.text()
)
def test_different_source_different_fingerprint(source1, source2, content_hash, style):
    assume(source1 != source2)
    fp1 = content_fingerprint(source1, content_hash, style_hash(style))
    fp2 = content_fingerprint(source2, content_hash, style_hash(style))
    assert fp1 != fp2
```

## Performance Profiling

### CPU Profiling

```python
# Add to app/main.py for profiling
import cProfile, pstats

if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        asyncio.run(main())
    finally:
        profiler.disable()
        stats = pstats.Stats(profiler).sort_stats('cumulative')
        stats.print_stats(20)
```

### Memory Profiling

```bash
# Install memory profiler
pip install memory-profiler

# Profile specific function
python -m memory_profiler app/services/content_service.py
```

### Async Profiling

```bash
# Install py-spy
pip install py-spy

# Profile running container
py-spy record -o profile.svg --pid <container_pid>
```

## Common Issues & Solutions

### Import Errors

```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH=/path/to/telegram-content-agent:$PYTHONPATH

# Or run from project root
cd /path/to/telegram-content-agent
python -m app.main
```

### Database Locked

```bash
# Check for other processes
lsof /data/style_memory.db

# Enable WAL mode for better concurrency
# In sqlite_repository.py initialize():
await db.execute("PRAGMA journal_mode=WAL;")
```

### Telegram Polling Conflicts

```bash
# Only one instance should poll
# Use drop_pending_updates=True
# For multiple instances: use webhook or single instance
```

### LLM Timeout Issues

```python
# Increase timeouts in .env
OLLAMA_TIMEOUT_SECONDS=180
GROQ_TIMEOUT_SECONDS=120
GEMINI_TIMEOUT_SECONDS=120
```

### Google Sheets Quota

```python
# Implement exponential backoff (already in place)
# Monitor: rate(sheets_writes_total{status="rate_limit"}[5m])
# Consider caching or batching for high volume
```

## Useful Commands

```bash
# Run specific test with output
pytest tests/unit/test_hashing.py::TestContentFingerprint::test_fingerprint_combines_all_parts -vvs

# Run tests matching pattern
pytest -k "duplicate" -v

# Run with coverage and open report
pytest --cov=app --cov-report=html && open htmlcov/index.html

# Type check specific file
mypy app/llm/orchestrator.py

# Lint specific file
ruff check app/bot/handlers.py

# Format code
ruff format app/ tests/

# Check for security issues
pip-audit -r requirements.txt

# Build Docker image
docker build -t telegram-content-agent:dev .

# Run container interactively
docker run -it --rm -v $(pwd):/app -v sqlite_data:/data telegram-content-agent:dev bash

# View database
sqlite3 /data/style_memory.db ".tables"
sqlite3 /data/style_memory.db "SELECT * FROM style_memory;"
sqlite3 /data/style_memory.db "SELECT fingerprint, status FROM idempotency_keys;"
```

## Architecture Diagrams

### Request Flow

```
Telegram Message
       │
       ▼
BotHandlers (route by type)
       │
       ▼
ContentRouter (detect type)
       │
       ├──► TextExtractor
       ├──► URLExtractor ──► trafilatura
       └──► PDFExtractor ──► MarkItDown
       │
       ▼
NormalizedContent
       │
       ▼
IdempotencyService (SQLite fingerprint)
       │
       ▼
LLMOrchestrator (provider fallback)
       │
       ▼
Pydantic Validation + JSON Recovery
       │
       ▼
SheetsRepository (cache + API)
       │
       ▼
Telegram Response
```

### Idempotency Flow

```
Request Received
       │
       ▼
Calculate Fingerprint
(source_id + content_hash + style_hash)
       │
       ▼
SQLite: INSERT fingerprint (PROCESSING)
       │
       ├── Exists & COMPLETED ──► DuplicateContentError
       ├── Exists & PROCESSING ──► Allow retry (stale)
       └── Exists & FAILED ──► Allow retry
       │
       ▼ (New)
LLM Generation
       │
       ▼
Sheets Cache Check
       │
       ├── In cache ──► DuplicateContentError
       │
       ▼
Sheets API: check_duplicate()
       │
       ├── Exists ──► DuplicateContentError
       │
       ▼
Sheets: append_row()
       │
       ▼
Update SQLite: COMPLETED
Update Cache
       │
       ▼
Success Response
```

## Resources

- [Python Telegram Bot Docs](https://docs.python-telegram-bot.org/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Structlog Docs](https://www.structlog.org/)
- [Trafilatura Docs](https://trafilatura.readthedocs.io/)
- [MarkItDown Docs](https://github.com/microsoft/markitdown)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Groq API](https://console.groq.com/docs)
- [Gemini API](https://ai.google.dev/docs)
- [Ollama Docs](https://github.com/ollama/ollama/blob/main/docs/api.md)