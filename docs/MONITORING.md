# Monitoring & Alerting Guide

Comprehensive monitoring strategy for the Telegram Content Agent.

## Overview

The service exposes structured logs and HTTP health endpoints. This guide covers:
- Key metrics to collect
- Log-based alerting patterns
- Dashboard recommendations
- Alert rules

## Metrics Collection

### Health Endpoints

```bash
# Liveness - process alive
curl http://localhost:8080/health
# {"status": "healthy", "service": "telegram-content-agent"}

# Readiness - dependencies ready
curl http://localhost:8080/ready
# {"status": "ready", "checks": {"database": "ok", "sheets": "ok", "llm_providers": {"ollama": true, "groq": true}}}
```

### Structured Logs

All logs are JSON with consistent fields:

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "info",
  "logger": "content_service",
  "request_id": "abc123",
  "user_id": 456,
  "content_type": "url",
  "event": "Processing content"
}
```

### Key Log Events

| Event | Logger | Fields | Significance |
|-------|--------|--------|--------------|
| `Processing content` | content_service | request_id, user_id, message_id | Request start |
| `Content routing failed` | content_service | request_id, error | Ingestion error |
| `Starting LLM generation` | llm_orchestrator | request_id, user_id, content_type, style_hash | LLM start |
| `Trying provider` | llm_orchestrator | provider, request_id | Provider attempt |
| `Provider failed, trying next` | llm_orchestrator | provider, error, request_id | Fallback triggered |
| `LLM generation successful` | llm_orchestrator | provider, request_id, title_length, x_length, linkedin_length | Success |
| `All LLM providers failed` | llm_orchestrator | request_id, last_error | Complete failure |
| `Row inserted` | sheets_repository | fingerprint, source | Sheets write success |
| `Duplicate detected` | sheets_repository | fingerprint | Idempotency hit |
| `Content processing complete` | content_service | request_id, fingerprint, is_new | Pipeline complete |
| `Content processing failed` | content_service | request_id, error | Pipeline error |

## Prometheus Metrics (Recommended)

Add to application for native metrics:

```python
# Add to app/main.py or new metrics module
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Request metrics
REQUESTS_TOTAL = Counter('telegram_requests_total', 'Total requests', ['content_type', 'status'])
REQUEST_DURATION = Histogram('telegram_request_duration_seconds', 'Request processing time')
CONCURRENT_REQUESTS = Gauge('telegram_concurrent_requests', 'Concurrent requests')

# LLM metrics
LLM_REQUESTS_TOTAL = Counter('llm_requests_total', 'LLM requests', ['provider', 'status'])
LLM_FALLBACK_TOTAL = Counter('llm_fallback_total', 'LLM fallbacks', ['from_provider', 'to_provider'])
LLM_DURATION = Histogram('llm_generation_duration_seconds', 'LLM generation time', ['provider'])

# Sheets metrics
SHEETS_WRITES_TOTAL = Counter('sheets_writes_total', 'Sheets writes', ['status'])
SHEETS_DURATION = Histogram('sheets_write_duration_seconds', 'Sheets write time')

# Idempotency metrics
IDEMPOTENCY_HITS = Counter('idempotency_hits_total', 'Idempotency cache hits', ['layer'])
DUPLICATE_REJECTIONS = Counter('duplicate_rejections_total', 'Duplicate rejections')

# Error metrics
ERRORS_TOTAL = Counter('errors_total', 'Total errors', ['component', 'error_type'])
```

### Instrumentation Example

```python
# In content_service.py
async def process_content(self, content_input):
    REQUESTS_TOTAL.labels(content_type=content_input.content_type.value, status="started").inc()
    CONCURRENT_REQUESTS.inc()
    start = time.time()
    
    try:
        # ... processing ...
        REQUESTS_TOTAL.labels(content_type=content_input.content_type.value, status="success").inc()
    except DuplicateContentError:
        REQUESTS_TOTAL.labels(content_type=content_input.content_type.value, status="duplicate").inc()
        DUPLICATE_REJECTIONS.inc()
    except Exception as e:
        REQUESTS_TOTAL.labels(content_type=content_input.content_type.value, status="error").inc()
        ERRORS_TOTAL.labels(component="content_service", error_type=type(e).__name__).inc()
        raise
    finally:
        REQUEST_DURATION.observe(time.time() - start)
        CONCURRENT_REQUESTS.dec()
```

## Log-Based Alerting (No Prometheus Required)

### Using grep/awk on Structured Logs

```bash
# Error rate in last 5 minutes
docker-compose logs app --since 5m | \
  jq -r 'select(.level == "error") | .logger' | \
  sort | uniq -c | sort -rn

# LLM fallback rate
docker-compose logs app --since 5m | \
  jq -r 'select(.event == "Provider failed, trying next") | .provider' | \
  wc -l

# Processing duration p95
docker-compose logs app --since 5m | \
  jq -r 'select(.event == "Content processing complete") | .duration' | \
  awk '{print $1}' | sort -n | awk '{a[NR]=$1} END {print a[int(NR*0.95)]}'

# Duplicate rejection spike
docker-compose logs app --since 5m | \
  jq -r 'select(.event == "Duplicate detected")' | wc -l
```

### Log Alert Patterns

| Pattern | Command | Alert If |
|---------|---------|----------|
| Health check down | `curl -f http://localhost:8080/health \|\| echo "DOWN"` | Exit code != 0 |
| Readiness down | `curl -f http://localhost:8080/ready \|\| echo "NOT_READY"` | Exit code != 0 |
| Error rate > 5% | `docker logs --since 5m app \| jq 'select(.level=="error")' \| wc -l` | > 10 errors/5m |
| LLM fallback > 20% | `docker logs --since 5m app \| jq 'select(.event=="Provider failed, trying next")' \| wc -l` | > 5 fallbacks/5m |
| Sheets errors | `docker logs --since 5m app \| jq 'select(.logger=="sheets_repository" and .level=="error")' \| wc -l` | > 0 |
| Processing > 60s | `docker logs --since 5m app \| jq 'select(.event=="Content processing complete" and .duration>60)' \| wc -l` | > 0 |
| Duplicate spike | `docker logs --since 5m app \| jq 'select(.event=="Duplicate detected")' \| wc -l` | > 50/5m |

## Dashboard Recommendations

### Grafana Dashboard Panels

```
Row 1: Overview
├── Request Rate (req/s) - stacked by content_type
├── Error Rate (%) - by component
├── P95 Latency (s) - overall
└── Active Requests (gauge)

Row 2: LLM Providers
├── Provider Success Rate (%) - per provider
├── Fallback Rate (%) - stacked from→to
├── Generation Duration (s) - per provider
└── Provider Health (status) - table

Row 3: Google Sheets
├── Write Rate (writes/s)
├── Write Duration (s) - p50/p95/p99
├── Duplicate Rejection Rate (%)
└── Cache Hit Rate (%)

Row 4: Idempotency
├── Local Cache Size (count)
├── SQLite Fingerprint States (PROCESSING/COMPLETED/FAILED)
├── Duplicate Rejections (count)
└── Stale Processing Cleanups (count)

Row 5: System
├── Container CPU/Memory
├── SQLite DB Size (MB)
├── Disk Usage (%)
└── Network I/O
```

### Loki/Elasticsearch Queries

```logql
# Error logs
{job="telegram-content-agent"} |= "error" | json | level="error"

# Slow requests
{job="telegram-content-agent"} | json | event="Content processing complete" | duration > 60

# Fallback chain
{job="telegram-content-agent"} | json | event="Provider failed, trying next"

# Duplicate tracking
{job="telegram-content-agent"} | json | event="Duplicate detected"
```

## Alert Rules

### Critical Alerts (Page Immediately)

```yaml
groups:
- name: telegram-content-agent-critical
  interval: 30s
  rules:
  - alert: ServiceDown
    expr: up{job="telegram-content-agent"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Telegram Content Agent is down"
      runbook: "https://github.com/.../OPERATIONS.md#bot-not-responding"

  - alert: HealthCheckFailing
    expr: probe_success{job="telegram-content-agent-health"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Health endpoint failing"

  - alert: ReadinessFailing
    expr: probe_success{job="telegram-content-agent-ready"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Service not ready - dependencies failing"

  - alert: AllLLMProvidersFailed
    expr: rate(llm_requests_total{status="all_failed"}[5m]) > 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "All LLM providers failed - no generation possible"
```

### Warning Alerts (Notify Within Hour)

```yaml
- name: telegram-content-agent-warning
  interval: 60s
  rules:
  - alert: HighErrorRate
    expr: rate(errors_total[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate: {{ $value | humanizePercentage }}"

  - alert: HighLLMFallbackRate
    expr: rate(llm_fallback_total[5m]) / rate(llm_requests_total[5m]) > 0.2
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "LLM fallback rate {{ $value | humanizePercentage }} - primary provider issues"

  - alert: SheetsAPIErrors
    expr: rate(sheets_writes_total{status="error"}[5m]) > 0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Google Sheets API errors detected"

  - alert: HighProcessingLatency
    expr: histogram_quantile(0.95, rate(telegram_request_duration_seconds_bucket[5m])) > 60
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "P95 processing latency {{ $value }}s exceeds 60s"

  - alert: DuplicateRejectionSpike
    expr: rate(duplicate_rejections_total[5m]) > 10
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Unusual duplicate rejection spike"

  - alert: DatabaseSizeGrowing
    expr: sqlite_db_size_bytes > 500000000
    for: 1h
    labels:
      severity: warning
    annotations:
      summary: "SQLite database > 500MB - consider cleanup"

  - alert: DiskSpaceLow
    expr: (node_filesystem_avail_bytes{mountpoint="/data"} / node_filesystem_size_bytes{mountpoint="/data"}) < 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Disk space < 10% on data volume"
```

### Info Alerts (Daily Digest)

```yaml
- name: telegram-content-agent-info
  interval: 1h
  rules:
  - alert: DailyStats
    expr: increase(telegram_requests_total[24h]) > 0
    for: 24h
    labels:
      severity: info
    annotations:
      summary: "Daily stats: {{ $value }} requests processed"
```

## Log Retention & Storage

### Docker Logging Driver

```yaml
# docker-compose.yml
services:
  app:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

### Centralized Logging

**Loki + Promtail:**
```yaml
# promtail-config.yaml
clients:
  - url: http://loki:3100/loki/api/v1/push

positions:
  filename: /tmp/positions.yaml

scrape_configs:
  - job_name: docker
    static_configs:
      - targets: [localhost]
        labels:
          job: telegram-content-agent
          __path__: /var/lib/docker/containers/*/*-json.log
```

**Elasticsearch/Filebeat:**
```yaml
# filebeat.yml
filebeat.inputs:
  - type: container
    paths:
      - /var/lib/docker/containers/*/*-json.log
    processors:
      - add_docker_metadata: ~
      - decode_json_fields:
          fields: ["log"]
          target: ""
          overwrite_keys: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
```

## Synthetic Monitoring

### Periodic End-to-End Test

```bash
#!/bin/bash
# synthetic-check.sh - Run every 5 minutes via cron

set -e

BOT_TOKEN="test_token"
CHAT_ID="test_chat_id"

# Send test message via Telegram API
RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d text="🧪 Synthetic monitoring test $(date -u +%H:%M:%S)")

MESSAGE_ID=$(echo "$RESPONSE" | jq -r '.result.message_id')

# Wait for processing
sleep 10

# Check Sheets for new row
# (Requires service account access)

# Alert if no new row
# ...

echo "Synthetic check passed"
```

### Health Endpoint Probes

```yaml
# Prometheus blackbox exporter
modules:
  http_2xx:
    prober: http
    timeout: 10s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2"]
      valid_status_codes: [200]
      method: GET
      headers:
        User-Agent: "prometheus-blackbox"
  http_ready:
    prober: http
    timeout: 10s
    http:
      valid_status_codes: [200, 503]
      method: GET
```

```yaml
# Prometheus scrape config
scrape_configs:
  - job_name: 'telegram-content-agent-health'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
        - http://telegram-content-agent:8080/health
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115

  - job_name: 'telegram-content-agent-ready'
    metrics_path: /probe
    params:
      module: [http_ready]
    static_configs:
      - targets:
        - http://telegram-content-agent:8080/ready
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: blackbox-exporter:9115
```

## Runbook Links

Each alert should link to relevant runbook section:

| Alert | Runbook Section |
|-------|----------------|
| ServiceDown | Bot Not Responding |
| HealthCheckFailing | Health Checks |
| ReadinessFailing | Health Checks |
| AllLLMProvidersFailed | High LLM Fallback Rate |
| HighErrorRate | Incident Response |
| SheetsAPIErrors | Google Sheets Operations |
| HighProcessingLatency | Performance Tuning |
| DuplicateRejectionSpike | Database Operations |

## Testing Alerts

```bash
# Test alert firing
curl -X POST http://alertmanager:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"TestAlert","severity":"critical","instance":"test"},"annotations":{"summary":"Test alert"}}]'

# Silence alert for maintenance
curl -X POST http://alertmanager:9093/api/v1/silences \
  -H "Content-Type: application/json" \
  -d '{"matchers":[{"name":"alertname","value":"ServiceDown","isRegex":false}],"startsAt":"2024-01-15T10:00:00Z","endsAt":"2024-01-15T12:00:00Z","createdBy":"admin","comment":"Planned maintenance"}'
```