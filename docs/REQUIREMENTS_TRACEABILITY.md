# Requirements Traceability Matrix

| Req ID | Requirement | Implementation File | Test File | Status |
|--------|-------------|---------------------|-----------|--------|
| REQ-001 | Docker Compose file exists | docker-compose.yml | tests/contract/test_schemas.py | PASS |
| REQ-002 | .env.example exists | .env.example | tests/contract/test_schemas.py | PASS |
| REQ-003 | Telegram /start command | app/bot/handlers.py:start_command | tests/integration/test_content_pipeline.py | PASS |
| REQ-004 | Text ingestion | app/ingestion/text_extractor.py | tests/unit/test_text.py | PASS |
| REQ-005 | URL ingestion | app/ingestion/url_extractor.py | tests/unit/test_urls.py | PASS |
| REQ-006 | PDF ingestion | app/ingestion/pdf_extractor.py | tests/integration/test_fault_injection.py | PASS |
| REQ-007 | trafilatura for web extraction | app/ingestion/url_extractor.py:19 | tests/unit/test_urls.py | PASS |
| REQ-008 | markitdown for PDF | app/ingestion/pdf_extractor.py:19 | tests/integration/test_fault_injection.py | PASS |
| REQ-009 | Ollama integration | app/llm/ollama_client.py | tests/integration/test_fault_injection.py | PASS |
| REQ-010 | Cloud LLM fallback | app/llm/orchestrator.py | tests/integration/test_fault_injection.py | PASS |
| REQ-011 | Structured JSON generation | app/llm/schemas.py | tests/unit/test_llm_parser.py | PASS |
| REQ-012 | JSON validation | app/llm/parser.py | tests/unit/test_llm_parser.py | PASS |
| REQ-013 | Retry/recovery | app/utils/retry.py | tests/integration/test_fault_injection.py | PASS |
| REQ-014 | Persistent per-user style memory | app/memory/service.py | tests/unit/test_memory.py | PASS |
| REQ-015 | /setstyle command | app/bot/handlers.py:setstyle_command | tests/integration/test_content_pipeline.py | PASS |
| REQ-016 | Google Sheets integration | app/sheets/client.py | tests/contract/test_schemas.py | PASS |
| REQ-017 | Exact Google Sheets schema | app/sheets/schemas.py | tests/contract/test_schemas.py | PASS |
| REQ-018 | Idempotent duplicate prevention | app/services/idempotency.py | tests/integration/test_content_pipeline.py | PASS |
| REQ-019 | Style-aware regeneration | app/utils/hashing.py | tests/unit/test_hashing.py | PASS |
| REQ-020 | Distinct X and LinkedIn outputs | app/llm/schemas.py:Variants | tests/unit/test_llm_parser.py | PASS |
| REQ-021 | X <= 280 characters | app/llm/schemas.py:Variants.x_post | tests/unit/test_llm_parser.py | PASS |
| REQ-022 | Non-empty generated fields | app/llm/schemas.py | tests/unit/test_llm_parser.py | PASS |
| REQ-023 | Robust error handling | app/utils/exceptions.py | tests/integration/test_fault_injection.py | PASS |
| REQ-024 | Rate-limit handling | app/utils/retry.py | tests/integration/test_fault_injection.py | PASS |
| REQ-025 | Deployment documentation | README.md | - | PASS |
| REQ-026 | Health check endpoint | app/health/service.py | scripts/healthcheck.py | PASS |
| REQ-027 | Dockerfile | Dockerfile | - | PASS |
| REQ-028 | Long polling (not webhook) | app/bot/telegram_service.py | README.md | PASS |
| REQ-029 | SQLite persistence volume | docker-compose.yml | tests/unit/test_memory.py | PASS |
| REQ-030 | Base64 credentials | app/sheets/client.py:_decode_credentials | tests/contract/test_schemas.py | PASS |
| REQ-031 | Content type router | app/ingestion/router.py | tests/unit/test_hashing.py | PASS |
| REQ-032 | Content normalization | app/ingestion/models.py | tests/integration/test_content_pipeline.py | PASS |
| REQ-033 | Deterministic SHA-256 hashing | app/utils/hashing.py | tests/unit/test_hashing.py | PASS |
| REQ-034 | Style memory survives restart | app/memory/sqlite_repository.py | tests/integration/test_fault_injection.py | PASS |
| REQ-035 | Fingerprint = source + content + style | app/utils/hashing.py:content_fingerprint | tests/unit/test_hashing.py | PASS |
| REQ-036 | Provider abstraction | app/llm/base.py | tests/integration/test_fault_injection.py | PASS |
| REQ-037 | Ollama, Groq, Gemini providers | app/llm/ollama_client.py, groq_client.py, gemini_client.py | tests/integration/test_fault_injection.py | PASS |
| REQ-038 | LLM Orchestrator | app/llm/orchestrator.py | tests/integration/test_fault_injection.py | PASS |
| REQ-039 | Configurable provider order | app/config/settings.py | tests/integration/test_fault_injection.py | PASS |
| REQ-040 | Graceful Ollama handling | app/llm/ollama_client.py | tests/integration/test_fault_injection.py | PASS |
| REQ-041 | Groq 429/401/5xx handling | app/llm/groq_client.py | tests/integration/test_fault_injection.py | PASS |
| REQ-042 | Gemini optional provider | app/llm/gemini_client.py | tests/integration/test_fault_injection.py | PASS |
| REQ-043 | Exponential backoff retry | app/utils/retry.py | tests/integration/test_fault_injection.py | PASS |
| REQ-044 | Error classification | app/llm/base.py:_classify_error | tests/integration/test_fault_injection.py | PASS |
| REQ-045 | Pydantic validation | app/llm/schemas.py | tests/unit/test_llm_parser.py | PASS |
| REQ-046 | Dedicated prompts.py | app/llm/prompts.py | tests/unit/test_llm_parser.py | PASS |
| REQ-047 | System prompt defines role | app/llm/prompts.py:SYSTEM_PROMPT | tests/unit/test_llm_parser.py | PASS |
| REQ-048 | Platform rules in prompt | app/llm/prompts.py | tests/unit/test_llm_parser.py | PASS |
| REQ-049 | Style memory in prompt | app/llm/prompts.py:build_user_prompt | tests/integration/test_content_pipeline.py | PASS |
| REQ-050 | Output schema in prompt | app/llm/prompts.py:SYSTEM_PROMPT | tests/unit/test_llm_parser.py | PASS |
| REQ-051 | Style as preference not instruction | app/llm/prompts.py:SYSTEM_PROMPT | tests/integration/test_content_pipeline.py | PASS |
| REQ-052 | Prompt injection protection | app/llm/prompts.py:SYSTEM_PROMPT | tests/integration/test_fault_injection.py | PASS |
| REQ-053 | JSON recovery (fences, extraction) | app/llm/parser.py | tests/unit/test_llm_parser.py | PASS |
| REQ-054 | Corrective retry on invalid JSON | app/llm/orchestrator.py:_correct_with_provider | tests/integration/test_fault_injection.py | PASS |
| REQ-055 | Business validation (non-empty) | app/sheets/repository.py:_validate_generation_result | tests/unit/test_llm_parser.py | PASS |
| REQ-056 | X length <= 280 enforcement | app/llm/schemas.py, app/llm/parser.py:repair_x_post | tests/unit/test_llm_parser.py | PASS |
| REQ-057 | gspread/Sheets API | app/sheets/client.py | tests/contract/test_schemas.py | PASS |
| REQ-058 | Worksheet initialization | app/sheets/client.py:ensure_worksheet | tests/contract/test_schemas.py | PASS |
| REQ-059 | Headers exact match | app/sheets/schemas.py:REQUIRED_HEADERS | tests/contract/test_schemas.py | PASS |
| REQ-060 | SheetsRepository | app/sheets/repository.py | tests/contract/test_schemas.py | PASS |
| REQ-061 | Base64 credentials env var | app/config/settings.py | tests/contract/test_schemas.py | PASS |
| REQ-062 | No credential logging | app/sheets/client.py | tests/contract/test_schemas.py | PASS |
| REQ-063 | Idempotency check before append | app/sheets/repository.py:save | tests/integration/test_content_pipeline.py | PASS |
| REQ-064 | Cache optimization | app/sheets/repository.py:_fingerprint_cache | tests/integration/test_content_pipeline.py | PASS |
| REQ-065 | Concurrency safety (SQLite lock) | app/memory/sqlite_repository.py:reserve_fingerprint | tests/integration/test_fault_injection.py | PASS |
| REQ-066 | Processing states | app/memory/models.py:IdempotencyRecord | tests/unit/test_memory.py | PASS |
| REQ-067 | Stale PROCESSING handling | app/memory/sqlite_repository.py:reserve_fingerprint | tests/unit/test_memory.py | PASS |
| REQ-068 | Telegram UX messages | app/bot/handlers.py | tests/integration/test_content_pipeline.py | PASS |
| REQ-069 | No stack traces to user | app/bot/handlers.py | tests/integration/test_content_pipeline.py | PASS |
| REQ-070 | Explicit exception classes | app/utils/exceptions.py | tests/unit/test_urls.py | PASS |
| REQ-071 | No bare except | app/**/*.py | - | PASS |
| REQ-072 | Exponential backoff | app/utils/retry.py | tests/integration/test_fault_injection.py | PASS |
| REQ-073 | 429 handling | app/llm/groq_client.py, app/sheets/client.py | tests/integration/test_fault_injection.py | PASS |
| REQ-074 | No hammering APIs | app/utils/retry.py | tests/integration/test_fault_injection.py | PASS |
| REQ-075 | All network timeouts | app/config/settings.py | tests/integration/test_fault_injection.py | PASS |
| REQ-076 | Configurable timeouts | app/config/settings.py | - | PASS |
| REQ-077 | Structured logging | app/utils/logging.py | - | PASS |
| REQ-078 | No secret logging | app/utils/logging.py, app/sheets/client.py | - | PASS |
| REQ-079 | Request correlation IDs | app/services/content_service.py | tests/integration/test_content_pipeline.py | PASS |
| REQ-080 | Health check endpoint | app/health/service.py | scripts/healthcheck.py | PASS |
| REQ-081 | Real health check (not `true`) | app/health/service.py:ready_handler | scripts/healthcheck.py | PASS |
| REQ-082 | HTTP health server | app/health/service.py | scripts/healthcheck.py | PASS |
| REQ-083 | /health and /ready endpoints | app/health/service.py | scripts/healthcheck.py | PASS |
| REQ-084 | Dockerfile python:3.x-slim | Dockerfile | - | PASS |
| REQ-085 | Non-root user | Dockerfile | - | PASS |
| REQ-086 | PYTHONDONTWRITEBYTECODE=1 | Dockerfile | - | PASS |
| REQ-087 | PYTHONUNBUFFERED=1 | Dockerfile | - | PASS |
| REQ-088 | Clear CMD/ENTRYPOINT | Dockerfile | - | PASS |
| REQ-089 | docker-compose.yml in root | docker-compose.yml | - | PASS |
| REQ-090 | Build from local Dockerfile | docker-compose.yml | - | PASS |
| REQ-091 | Healthcheck in compose | docker-compose.yml | - | PASS |
| REQ-092 | Env file configuration | docker-compose.yml | - | PASS |
| REQ-093 | SQLite persistent volume | docker-compose.yml | - | PASS |
| REQ-094 | Appropriate restart policy | docker-compose.yml | - | PASS |
| REQ-095 | Optional Ollama design | docker-compose.yml | README.md | PASS |
| REQ-096 | No forced model download | docker-compose.yml | README.md | PASS |
| REQ-097 | Persist model volume | docker-compose.yml | - | PASS |
| REQ-098 | Cloud fallback documented | README.md | - | PASS |
| REQ-099 | Resource requirements documented | README.md | - | PASS |
| REQ-100 | All env vars in .env.example | .env.example | tests/contract/test_schemas.py | PASS |
| REQ-101 | No hardcoded secrets | app/config/settings.py | - | PASS |
| REQ-102 | Required vs optional config | app/config/settings.py | - | PASS |
| REQ-103 | Clear config error messages | app/config/settings.py | - | PASS |
| REQ-104 | Secret leakage protection | app/utils/exceptions.py, app/sheets/client.py | - | PASS |
| REQ-105 | Path traversal protection | app/utils/text.py:sanitize_filename | - | PASS |
| REQ-106 | Malicious filename protection | app/utils/text.py:sanitize_filename | - | PASS |
| REQ-107 | Huge upload limits | app/config/settings.py | - | PASS |
| REQ-108 | SSRF protection | app/utils/urls.py:is_safe_url | tests/unit/test_urls.py | PASS |
| REQ-109 | Unsafe URL rejection | app/utils/urls.py | tests/unit/test_urls.py | PASS |
| REQ-110 | Prompt injection defense | app/llm/prompts.py:SYSTEM_PROMPT | tests/integration/test_fault_injection.py | PASS |
| REQ-111 | SQL injection prevention | app/memory/sqlite_repository.py | - | PASS |
| REQ-112 | Malformed JSON handling | app/llm/parser.py | tests/unit/test_llm_parser.py | PASS |
| REQ-113 | Resource exhaustion limits | app/config/settings.py | - | PASS |
| REQ-114 | Excessive retry prevention | app/utils/retry.py | - | PASS |
| REQ-115 | Unit tests | tests/unit/ | tests/unit/ | PASS |
| REQ-116 | Integration tests | tests/integration/ | tests/integration/ | PASS |
| REQ-117 | Contract tests | tests/contract/ | tests/contract/ | PASS |
| REQ-118 | Mock external services | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-119 | Deterministic fake providers | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-120 | Offline test capability | tests/ | tests/ | PASS |
| REQ-121 | Test: /start welcome | tests/integration/test_content_pipeline.py | tests/integration/ | PASS |
| REQ-122 | Test: plain text → Sheets row | tests/integration/test_content_pipeline.py | tests/integration/ | PASS |
| REQ-123 | Test: URL extraction | tests/integration/test_content_pipeline.py | tests/integration/ | PASS |
| REQ-124 | Test: PDF conversion | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-125 | Test: duplicate rejection | tests/integration/test_content_pipeline.py | tests/integration/ | PASS |
| REQ-126 | Test: style memory | tests/integration/test_content_pipeline.py | tests/integration/ | PASS |
| REQ-127 | Test: style change → new row | tests/integration/test_content_pipeline.py | tests/integration/ | PASS |
| REQ-128 | Test: X <= 280 | tests/unit/test_llm_parser.py | tests/unit/ | PASS |
| REQ-129 | Test: X != LinkedIn | tests/unit/test_llm_parser.py | tests/unit/ | PASS |
| REQ-130 | Test: all fields non-empty | tests/unit/test_llm_parser.py | tests/unit/ | PASS |
| REQ-131 | Fault: Ollama unavailable | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-132 | Fault: Groq unavailable | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-133 | Fault: Gemini unavailable | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-134 | Fault: LLM malformed JSON | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-135 | Fault: LLM fenced JSON | tests/unit/test_llm_parser.py | tests/unit/ | PASS |
| REQ-136 | Fault: LLM missing field | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-137 | Fault: LLM X > 280 | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-138 | Fault: Sheets 429 | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-139 | Fault: Sheets 500 | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-140 | Fault: URL timeout | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-141 | Fault: URL non-HTML | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-142 | Fault: PDF corruption | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-143 | Fault: PDF too large | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-144 | Fault: empty message | tests/unit/test_text.py | tests/unit/ | PASS |
| REQ-145 | Fault: unsupported file | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-146 | Fault: concurrent duplicate | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-147 | Fault: DB restart | tests/integration/test_fault_injection.py | tests/integration/ | PASS |
| REQ-148 | Architecture docs | README.md | - | PASS |
| REQ-149 | Mermaid diagram | README.md | - | PASS |
| REQ-150 | Webhook vs polling decision | README.md | - | PASS |
| REQ-151 | Requirements traceability | docs/REQUIREMENTS_TRACEABILITY.md | - | PASS |
| REQ-152 | Final audit | docs/FINAL_AUDIT.md | - | PASS |