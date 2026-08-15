# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-15

### Added

#### Core Features
- Telegram bot with long polling (`/start`, `/setstyle`, `/getstyle`, `/clearstyle`)
- Multi-format content ingestion:
  - Plain text processing with normalization
  - URL extraction using trafilatura (with SSRF protection)
  - PDF extraction using Microsoft MarkItDown
- Persistent per-user style memory (SQLite)
- LLM orchestration with provider fallback:
  - Ollama (local, primary)
  - Groq (cloud fallback)
  - Google Gemini (cloud fallback)
- Structured JSON output with Pydantic validation
- Google Sheets integration with exact schema compliance
- Style-aware idempotency (fingerprint = source + content + style)
- X post validation (≤280 chars with repair/regeneration)
- Distinct X and LinkedIn variants enforcement
- Comprehensive health checks (`/health`, `/ready`, `/live`)

#### Architecture
- Clean layered architecture (config, bot, ingestion, llm, memory, sheets, services, utils, health)
- Dependency injection throughout
- Async-first design with blocking operations offloaded
- Protocol-based LLM provider abstraction
- Explicit exception hierarchy for precise error handling
- Structured JSON logging with request correlation IDs

#### Resilience
- Exponential backoff retry with jitter
- Error classification (transient, rate-limit, auth, validation, permanent)
- Provider health checks
- Stale PROCESSING state recovery
- Timeout enforcement on all network operations
- Circuit breaker pattern via fallback chain

#### Testing
- 121 tests passing (49 unit, 23 integration, 9 contract, 40 fault injection)
- Deterministic fake providers for offline testing
- Contract tests for exact schema compliance
- Fault injection for 20+ failure scenarios
- Property-based testing ready (hypothesis)

#### Security
- SSRF protection (blocks localhost, private IPs, .local domains)
- Input validation at all boundaries
- Parameterized SQL queries
- Path traversal prevention
- Base64-encoded credentials (never on disk)
- Non-root Docker container
- Structured logging with secret exclusion

#### Documentation
- Comprehensive README with architecture diagrams
- Deployment guides (Docker, Fly.io, Railway, Render, AWS, GCP, K8s)
- Operations runbook
- Architecture Decision Records (12 ADRs)
- Monitoring & alerting guide
- Developer guide
- Security policy
- Contributing guide
- Requirements traceability matrix (152 requirements)
- Final audit report (100/100)

#### DevOps
- Multi-stage Dockerfile (python:3.12-slim)
- docker-compose with healthchecks and volumes
- .env.example with 68 documented variables
- GitHub Actions ready CI/CD
- Prometheus metrics instrumentation points
- Blackbox exporter probes for health endpoints

### Fixed
- All linting issues (59 ruff violations resolved)
- Type checking errors (mypy clean)
- datetime.utcnow() deprecation warnings (timezone-aware)
- Broad exception handling (specific exceptions only)
- Async file I/O blocking (offloaded to thread pool)
- Import sorting and formatting

### Security
- No hardcoded secrets
- No credential logging
- Minimal service account permissions documented
- Supply chain scanning (pip-audit)

## [0.9.0] - 2024-01-10 (Pre-release)

### Added
- Initial project structure
- Basic Telegram bot with /start
- Text and URL ingestion
- Ollama integration
- Google Sheets writing
- SQLite style memory

### Known Issues
- No PDF support
- No idempotency
- No fallback providers
- Basic error handling

## [0.1.0] - 2024-01-01 (Initial)

### Added
- Repository initialization
- Basic project structure
- Requirements and configuration


## Upgrade Guide

### From 0.9.0 to 1.0.0

#### Breaking Changes
- Database schema changed (added idempotency_keys table) - run migration or delete volume
- Environment variables added (see .env.example)
- Health check endpoints changed (/health, /ready, /live)

#### Migration Steps
1. Backup SQLite database: `cp /data/style_memory.db /backup/style_memory.db.backup`
2. Update .env with new variables
3. Rebuild containers: `docker-compose build --no-cache`
4. Start: `docker-compose up -d`
5. Verify: `curl http://localhost:8080/health && curl http://localhost:8080/ready`

#### New Features to Configure
- Set `GROQ_API_KEY` and/or `GEMINI_API_KEY` for fallback
- Configure `LLM_PRIMARY_PROVIDER` and `LLM_FALLBACK_PROVIDERS`
- Review timeout settings for your environment

## Release Notes Format

Each release includes:
- **Added** - New features
- **Changed** - Changes in existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Vulnerability fixes


## Links

- [GitHub Releases](https://github.com/your-org/telegram-content-agent/releases)
- [Documentation](https://github.com/your-org/telegram-content-agent/tree/main/docs)
- [Issues](https://github.com/your-org/telegram-content-agent/issues)