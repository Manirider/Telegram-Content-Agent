# Contributing Guide

Thank you for contributing to the Telegram Content Agent!

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Follow the project's coding standards
- Test your changes thoroughly

## Development Setup

### Prerequisites

- Python 3.12+
- Docker & docker-compose
- Git

### Local Environment

```bash
# Clone repository
git clone https://github.com/your-org/telegram-content-agent.git
cd telegram-content-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install

# Copy environment template
cp .env.example .env
# Edit .env with your test credentials
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html --cov-report=term

# Specific test types
pytest -m unit        # Unit tests only
pytest -m integration # Integration tests only
pytest -m contract    # Contract tests only

# Verbose output
pytest -v --tb=short

# Run specific test file
pytest tests/unit/test_hashing.py -v

# Run with pattern matching
pytest -k "test_duplicate" -v
```

### Code Quality Checks

```bash
# Linting (ruff)
ruff check app/ tests/
ruff check --fix app/ tests/  # Auto-fix

# Type checking (mypy)
mypy app/

# Format check
ruff format --check app/ tests/
ruff format app/ tests/  # Auto-format
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.7
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-pyyaml]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
```

## Project Structure

```
telegram-content-agent/
├── app/
│   ├── main.py                 # Entry point
│   ├── config/                 # Settings & config
│   ├── bot/                    # Telegram handlers
│   ├── ingestion/              # Content extraction
│   ├── llm/                    # LLM providers & orchestration
│   ├── memory/                 # SQLite persistence
│   ├── sheets/                 # Google Sheets integration
│   ├── services/               # Business logic
│   ├── utils/                  # Shared utilities
│   └── health/                 # Health endpoints
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── contract/               # Contract tests
│   └── fixtures/               # Test data
├── docs/                       # Documentation
├── scripts/                    # Operational scripts
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pytest.ini
```

## Coding Standards

### Python Style

- **Type hints**: Required for all public functions
- **Docstrings**: Google style for public APIs
- **Line length**: 100 chars (ruff default)
- **Imports**: Sorted (stdlib, third-party, local)
- **Naming**: snake_case for functions/variables, PascalCase for classes

### Type Hints

```python
# Good
async def process_content(
    self,
    content_input: ContentInput,
) -> tuple[bool, str, ContentGenerationResult | None]:
    ...

# Avoid
async def process_content(self, content_input):
    ...
```

### Error Handling

```python
# Use explicit exceptions
from app.utils.exceptions import ValidationError, IngestionError

# Good - specific exception
raise ValidationError("Style prompt cannot be empty")

# Avoid - generic exception
raise Exception("Style prompt cannot be empty")

# Catch specific exceptions
try:
    await self.memory_service.set_style(user_id, style_prompt)
except ValidationError as e:
    # Handle validation error
    pass
except (OSError, RuntimeError) as e:
    # Handle system errors
    logger.error("Failed to set style", error=str(e))
```

### Async Patterns

```python
# Use async context managers
async with aiosqlite.connect(db_path) as db:
    async with db.execute("SELECT ...") as cursor:
        ...

# Offload blocking I/O
result = await asyncio.to_thread(blocking_function, arg)

# Proper timeout handling
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url)
```

### Logging

```python
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Structured logging with context
logger.info(
    "Processing content",
    request_id=request_id,
    user_id=user_id,
    content_type=content_type.value,
)

# Error logging with exception info
logger.error(
    "Content processing failed",
    request_id=request_id,
    error=str(e),
    exc_info=True,  # Includes traceback
)
```

## Testing Guidelines

### Unit Tests

- Test single functions/classes in isolation
- Use mocks for external dependencies
- Target >90% coverage for business logic

```python
# tests/unit/test_example.py
import pytest
from app.utils.hashing import content_fingerprint

class TestContentFingerprint:
    def test_combines_all_parts(self):
        fp1 = content_fingerprint("src1", "hash1", "style1")
        fp2 = content_fingerprint("src1", "hash1", "style2")
        assert fp1 != fp2  # Different style = different fingerprint
    
    def test_deterministic(self):
        fp1 = content_fingerprint("src", "hash", "style")
        fp2 = content_fingerprint("src", "hash", "style")
        assert fp1 == fp2
```

### Integration Tests

- Test component interactions
- Use fake implementations for external services
- Test full pipelines

```python
# tests/integration/test_example.py
@pytest.mark.asyncio
async def test_full_pipeline(content_service, memory_service):
    content_input = ContentInput(...)
    is_new, fingerprint, result = await content_service.process_content(content_input)
    assert is_new is True
    assert result is not None
```

### Contract Tests

- Verify exact API contracts
- Schema validation
- External interface compliance

```python
# tests/contract/test_example.py
def test_required_headers_exact(self):
    expected = ["SourceIdentifier", "SubmissionTimestamp", ...]
    assert REQUIRED_HEADERS == expected
```

### Fixtures

```python
# tests/conftest.py
@pytest.fixture
async def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    yield repo
    await repo.close()
    os.unlink(db_path)
```

## Pull Request Process

### Before Submitting

1. **Run all checks locally**:
   ```bash
   ruff check app/ tests/
   mypy app/
   pytest
   ```

2. **Update documentation** if changing:
   - Public APIs
   - Configuration options
   - Architecture decisions

3. **Add tests** for:
   - New features
   - Bug fixes
   - Edge cases

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Contract tests pass
- [ ] Manual testing done

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Dependencies justified
```

### Review Criteria

- Code quality & style
- Test coverage
- Performance impact
- Security considerations
- Backward compatibility
- Documentation completeness

## Release Process

### Versioning

Semantic Versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes (backward compatible)

### Release Steps

1. Update version in `pyproject.toml` / `setup.py`
2. Update `CHANGELOG.md`
3. Create release branch: `release/vX.Y.Z`
4. Run full test suite
5. Build Docker image: `docker build -t telegram-content-agent:vX.Y.Z .`
5. Tag release: `git tag vX.Y.Z`
6. Push tag: `git push origin vX.Y.Z`
7. GitHub Actions builds & publishes
8. Update deployment docs if needed

## Adding New LLM Providers

1. Implement `LLMProvider` protocol in `app/llm/new_provider.py`
2. Add to `LLMOrchestrator._initialize_providers()`
3. Add configuration to `app/config/settings.py`
4. Add environment variables to `.env.example`
5. Add tests in `tests/unit/test_new_provider.py`
6. Update `README.md` with provider info

## Adding New Content Types

1. Add `ContentType` enum value in `app/ingestion/models.py`
2. Create extractor in `app/ingestion/new_extractor.py`
3. Register in `ContentRouter._detect_content_type()`
4. Add validation in `app/sheets/schemas.py`
5. Add tests for ingestion pipeline
6. Update `README.md`

## Security Considerations

- Never commit secrets or credentials
- Validate all external inputs
- Use parameterized queries (no SQL injection)
- Sanitize file paths (no path traversal)
- Limit resource consumption (timeouts, size limits)
- Report security issues privately

## Getting Help

- Check existing issues/PRs
- Read documentation in `docs/`
- Ask in discussions
- Tag maintainers for urgent issues

## Recognition

Contributors will be acknowledged in:
- `CONTRIBUTORS.md`
- Release notes
- Project README