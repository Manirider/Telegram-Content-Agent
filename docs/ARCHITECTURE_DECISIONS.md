# Architecture Decision Records (ADRs)

## ADR-001: Long Polling over Webhooks

**Status**: Accepted
**Date**: 2024-01-15

### Context

Telegram bots can receive updates via:
1. **Webhooks**: Telegram POSTs to a public HTTPS endpoint
2. **Long Polling**: Bot initiates HTTP requests to Telegram's `getUpdates` API

### Decision

Use **Long Polling** as the primary update mechanism.

### Rationale

| Factor | Webhooks | Long Polling |
|--------|----------|--------------|
| Free-tier cold starts | Fails (no public endpoint when sleeping) | Works (bot initiates connection) |
| Public HTTPS required | Yes (SSL cert, domain, reverse proxy) | No |
| Deployment complexity | High (nginx, cert-manager, DNS) | Low (single container) |
| Latency | ~50ms lower | Negligible for this use case |
| Connection management | Telegram manages | Bot manages (auto-reconnect) |
| Rate limits | N/A | Built-in backoff |

### Consequences

- **Positive**: Works on free tiers (Fly.io, Railway, Render) that sleep on inactivity
- **Positive**: Simpler deployment, no SSL/cert management
- **Positive**: Automatic reconnection on network issues
- **Negative**: Slightly higher latency (acceptable for content generation)
- **Negative**: Constant connection (minimal resource usage)

### Implementation

```python
# app/bot/telegram_service.py
await self.application.updater.start_polling(
    drop_pending_updates=True,
    allowed_updates=["message", "edited_message"],
)
```

### Alternatives Considered

- Webhook with cloud function (adds cost/complexity)
- Webhook with ngrok/tunnel (unreliable for production)
- Hybrid: Webhook primary, polling fallback (complexity not justified)

---

## ADR-002: SQLite for Persistence

**Status**: Accepted
**Date**: 2024-01-15

### Context

Need persistent storage for:
- User style preferences
- Idempotency tracking (fingerprints with PROCESSING/COMPLETED/FAILED states)

### Decision

Use **SQLite** with a Docker named volume.

### Rationale

| Requirement | SQLite | PostgreSQL | Redis + SQLite |
|-------------|--------|------------|----------------|
| Zero config | ✅ | ❌ | ❌ |
| Single-file backup | ✅ | ❌ | ❌ |
| ACID transactions | ✅ | ✅ | Partial |
| Concurrent writes | Limited | ✅ | ✅ |
| Docker volume persistence | ✅ | ✅ | ✅ |
| Operational overhead | None | High | Medium |

### Consequences

- **Positive**: No separate database server needed
- **Positive**: Simple backup/restore (copy file)
- **Positive**: Works with Docker volumes natively
- **Negative**: Single-writer limitation (mitigated by single-instance deployment)
- **Negative**: Not suitable for horizontal scaling without changes

### Mitigations

- Use WAL mode for better concurrency
- Application-level locking via UNIQUE constraints
- For scaling: migrate to PostgreSQL with minimal schema changes

---

## ADR-003: Style-Aware Idempotency Fingerprint

**Status**: Accepted
**Date**: 2024-01-15

### Context

Requirement: Same URL + different style = new row. Naive URL-only deduplication breaks this.

### Decision

Fingerprint = SHA256(source_identifier + content_hash + style_hash)

Where:
- **Text/PDF**: content_hash = SHA256(normalized_content)
- **URL**: source_identifier = original URL (as required by spec)
- **style_hash**: SHA256(style_prompt) or "no-style"

### Rationale

| Approach | Same URL + Same Style | Same URL + Diff Style | URL Content Changed |
|----------|----------------------|----------------------|---------------------|
| URL only | ✅ Duplicate | ❌ Should be new | ❌ Should be new |
| URL + Style | ✅ Duplicate | ✅ New row | ❌ Should be new |
| **Full fingerprint** | ✅ Duplicate | ✅ New row | ✅ New row |

### Implementation

```python
# app/utils/hashing.py
def content_fingerprint(source_identifier: str, content_hash: str, style_hash: str) -> str:
    combined = f"{source_identifier}|{content_hash}|{style_hash}"
    return sha256_hash(combined)

def style_hash(style_prompt: str | None) -> str:
    if not style_prompt or not style_prompt.strip():
        return "no-style"
    return sha256_hash(style_prompt.strip())
```

### Concurrency Safety

- SQLite UNIQUE constraint on fingerprint
- States: PROCESSING → COMPLETED/FAILED
- Stale PROCESSING records auto-reset on retry

---

## ADR-004: LLM Provider Abstraction with Fallback Chain

**Status**: Accepted
**Date**: 2024-01-15

### Context

Need resilient LLM generation with:
- Local (Ollama) as primary for cost/privacy
- Cloud (Groq, Gemini) as fallback
- Configurable provider order

### Decision

Implement `LLMProvider` protocol with concrete providers and `LLMOrchestrator` for fallback.

### Architecture

```python
# app/llm/base.py
class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...
    async def generate(self, request: LLMRequest) -> ContentGenerationResult: ...
    async def health_check(self) -> bool: ...
    async def close(self) -> None: ...
```

### Fallback Logic

```
Primary (Ollama) 
  → Retry 3x with exponential backoff
    → Fallback 1 (Groq)
      → Retry 3x
        → Fallback 2 (Gemini)
          → Retry 3x
            → Fail with aggregated error
```

### Error Classification

| Category | Examples | Action |
|----------|----------|--------|
| Transient | Timeout, 5xx, connection error | Retry + fallback |
| Rate Limit | 429, quota exceeded | Retry with longer backoff |
| Auth | 401, 403, invalid key | No retry, fallback |
| Validation | Bad JSON, schema mismatch | Corrective retry once |
| Permanent | Model not found | No retry, fallback |

### Consequences

- **Positive**: Graceful degradation when providers fail
- **Positive**: No single point of failure
- **Positive**: Configurable via env vars
- **Negative**: Added complexity in orchestration

---

## ADR-005: Structured JSON Output with Pydantic Validation

**Status**: Accepted
**Date**: 2024-01-15

### Context

LLM must produce structured output for Google Sheets with strict schema.

### Decision

Use Pydantic models for validation + multi-stage JSON recovery.

### Schema

```python
# app/llm/schemas.py
class Variants(BaseModel):
    x_post: str = Field(..., max_length=280)
    linkedin_post: str = Field(..., min_length=1)

class ContentGenerationResult(BaseModel):
    title: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    variants: Variants
```

### Recovery Pipeline

1. Direct `json.loads()`
2. Extract from markdown fences (```json```)
3. Extract JSON object from mixed text
4. Corrective retry with error feedback
5. Fallback to next provider

### X Post Length Enforcement

1. Pydantic validates ≤280 at construction
2. Business validation double-checks
3. `repair_x_post()` truncates at word boundary
4. Hard truncation with ellipsis as final safeguard

---

## ADR-006: Google Sheets Idempotency with Local Cache

**Status**: Accepted
**Date**: 2024-01-15

### Context

Prevent duplicate rows while maintaining consistency with Sheets as source of truth.

### Decision

Two-layer idempotency:
1. **Local SQLite**: Fingerprint reservation with PROCESSING/COMPLETED/FAILED states
2. **Sheets**: Fingerprint cache (column A) + verification before insert

### Flow

```
1. Reserve fingerprint in SQLite (atomic INSERT with UNIQUE)
   → If COMPLETED: raise DuplicateContentError
   → If PROCESSING/FAILED: allow retry
   
2. Generate content via LLM

3. Check Sheets cache
   → If in cache: mark FAILED locally, raise DuplicateContentError
   
4. Verify with Sheets API (source of truth)
   → If exists: update cache, raise DuplicateContentError
   
5. Append row to Sheets
   → Update local cache
   → Mark COMPLETED in SQLite
```

### Cache Invalidation

- Invalidate on Sheets write errors
- Periodic refresh on startup
- TTL-based expiration (future enhancement)

---

## ADR-007: Health Check HTTP Server Alongside Long Polling

**Status**: Accepted
**Date**: 2024-01-15

### Context

Docker healthcheck requires HTTP endpoint, but long polling doesn't expose HTTP.

### Decision

Run lightweight aiohttp server on port 8080 for `/health`, `/ready`, `/live`.

### Endpoints

| Endpoint | Purpose | Dependencies Checked |
|----------|---------|---------------------|
| `/health` | Liveness | None (process alive) |
| `/live` | K8s liveness | None |
| `/ready` | Readiness | Database, Sheets auth, LLM providers |

### Implementation

```python
# app/health/service.py
class HealthService:
    async def start(self):
        self.app = web.Application()
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/ready", self.ready_handler)
        self.app.router.add_get("/live", self.live_handler)
        # ... run on 0.0.0.0:8080
```

### Docker Healthcheck

```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 15s
```

---

## ADR-008: Prompt Engineering with System/User Separation

**Status**: Accepted
**Date**: 2024-01-15

### Context

Need consistent, high-quality LLM output with style memory integration.

### Decision

Structured prompt composition in `app/llm/prompts.py`:

```
SYSTEM INSTRUCTIONS (fixed)
+ PLATFORM RULES (X/LinkedIn constraints)
+ USER STYLE MEMORY (preference layer)
+ SOURCE CONTENT (untrusted)
+ OUTPUT SCHEMA (JSON format)
```

### Security Measures

- Style memory treated as **preference**, not instruction
- System constraints **always win** over style
- Source content marked as **untrusted** in prompt
- Explicit prompt injection defense in system prompt

### Style Memory Integration

```python
# app/llm/prompts.py
def build_user_prompt(content: NormalizedContent, style_prompt: str | None) -> str:
    parts = []
    if style_prompt:
        parts.append(f"USER STYLE PREFERENCE: {style_prompt}")
        parts.append("")
    parts.extend([
        f"SOURCE TYPE: {type_label}",
        f"SOURCE IDENTIFIER: {content.source_identifier}",
        "",
        "SOURCE CONTENT:",
        content.content,
        "",
        "Generate the structured JSON output now.",
    ])
    return "\n".join(parts)
```

---

## ADR-009: Async-First with Blocking Operations Offloaded

**Status**: Accepted
**Date**: 2024-01-15

### Context

Python-telegram-bot is async. Need to avoid blocking event loop.

### Decision

- Use async libraries throughout (httpx, aiosqlite, gspread async)
- Offload blocking ops (MarkItDown, file I/O) to thread pool

### Examples

```python
# PDF magic bytes check - offloaded
async def _read_file_header(self, file_path: str) -> bytes:
    def _read():
        with open(file_path, "rb") as f:
            return f.read(5)
    return await asyncio.to_thread(_read)

# MarkItDown conversion - runs in thread pool
result = await asyncio.to_thread(md.convert, file_path)
```

### Consequences

- Event loop stays responsive
- No blocking Telegram message processing
- Slight overhead for thread pool, acceptable for I/O-bound ops

---

## ADR-010: Base64-Encoded Service Account Credentials

**Status**: Accepted
**Date**: 2024-01-15

### Context

Google Sheets requires service account JSON. Must not commit to repo.

### Decision

Store as base64 in environment variable `GOOGLE_SHEETS_CREDENTIALS_B64`.

### Implementation

```python
# app/sheets/client.py
def _decode_credentials(self) -> dict:
    decoded = base64.b64decode(self.config.credentials_b64).decode("utf-8")
    return json.loads(decoded)

async def authenticate(self) -> None:
    creds_dict = self._decode_credentials()
    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    self.gc = gspread.authorize(credentials)
```

### Benefits

- No credential files on disk
- Works with all secret management systems (K8s secrets, Fly.io secrets, AWS Secrets Manager)
- Single environment variable to rotate
- Never logged (structlog excludes sensitive fields)

---

## ADR-011: Comprehensive Exception Hierarchy

**Status**: Accepted
**Date**: 2024-01-15

### Context

Need precise error handling for retry logic and user feedback.

### Decision

Explicit exception classes in `app/utils/exceptions.py`:

```
AppError
├── ConfigurationError
├── IngestionError
│   ├── ExtractionError
│   ├── UnsupportedContentError
│   ├── EmptyContentError
│   └── ContentTooLargeError
├── LLMError
│   ├── LLMValidationError
│   ├── ProviderUnavailableError
│   ├── RateLimitError
│   └── AuthenticationError
├── SheetsError
├── DuplicateContentError
├── IdempotencyError
├── ValidationError
└── HealthCheckError
```

### Retry Integration

```python
# app/utils/retry.py
def is_transient_error(exc: Exception) -> bool:
    if isinstance(exc, (ProviderUnavailableError, RateLimitError)):
        return True
    if isinstance(exc, LLMError) and "timeout" in str(exc).lower():
        return True
    if isinstance(exc, SheetsError) and "rate limit" in str(exc).lower():
        return True
    return isinstance(exc, (asyncio.TimeoutError, ConnectionError, TimeoutError))
```

---

## ADR-012: Structured JSON Logging with Structlog

**Status**: Accepted
**Date**: 2024-01-15

### Context

Need production-grade observability with request correlation.

### Decision

Use structlog with JSON renderer, contextvars for request ID propagation.

### Configuration

```python
# app/utils/logging.py
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
```

### Usage

```python
logger = get_logger(__name__)

# Automatic context propagation
logger.info("Processing content", request_id="abc123", user_id=456)

# Output:
# {"timestamp": "2024-01-15T10:30:00Z", "level": "info", "logger": "content_service", 
#  "request_id": "abc123", "user_id": 456, "event": "Processing content"}
```

### Secret Protection

```python
# Noisy libraries silenced
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
```

---

## Summary of Key Decisions

| ADR | Decision | Impact |
|-----|----------|--------|
| 001 | Long Polling | Free-tier compatible, simpler deployment |
| 002 | SQLite | Zero-config, easy backup, single-instance |
| 003 | Style-aware fingerprint | Correct deduplication with style changes |
| 004 | LLM fallback chain | Resilient generation, no single provider dependency |
| 005 | Pydantic + JSON recovery | Strict schema, handles LLM inconsistencies |
| 006 | Dual-layer idempotency | Consistency with performance |
| 007 | HTTP health server | Docker/K8s compatible healthchecks |
| 008 | Structured prompts | Secure, consistent LLM output |
| 009 | Async-first | Responsive bot, no blocked event loop |
| 010 | Base64 credentials | Secret-safe, platform-agnostic |
| 011 | Exception hierarchy | Precise retry/error handling |
| 012 | Structured logging | Production observability |