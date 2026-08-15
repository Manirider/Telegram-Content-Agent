# Operations Runbook

Day-to-day operational procedures for the Telegram Content Agent.

## Service Overview

| Aspect | Detail |
|--------|--------|
| Service Name | telegram-content-agent |
| Port | 8080 (HTTP health) |
| Protocol | Long polling (Telegram) |
| Database | SQLite (persistent volume) |
| External Dependencies | Telegram API, Google Sheets API, LLM Providers |

## Health Checks

### Liveness (`/health`)

```bash
curl -f http://localhost:8080/health
# Expected: {"status": "healthy", "service": "telegram-content-agent"}
```

- **Purpose**: Process is alive
- **Failure Action**: Container restart (handled by Docker/orchestrator)
- **Interval**: 30s

### Readiness (`/ready`)

```bash
curl -f http://localhost:8080/ready
# Expected: {"status": "ready", "checks": {...}}
```

- **Purpose**: Critical dependencies initialized
- **Checks**: Database connectivity, Sheets auth, LLM providers
- **Failure Action**: Remove from load balancer / don't route traffic
- **Interval**: 10s

## Common Operations

### View Logs

```bash
# Docker Compose
docker-compose logs -f app

# Kubernetes
kubectl logs -f deployment/telegram-content-agent

# Fly.io
fly logs -a telegram-content-agent

# Filter by level
docker-compose logs app | grep -i error
```

### Restart Service

```bash
# Docker Compose
docker-compose restart app

# Kubernetes
kubectl rollout restart deployment/telegram-content-agent

# Fly.io
fly apps restart telegram-content-agent
```

### Check Status

```bash
# Container status
docker-compose ps

# Health endpoints
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

## Database Operations

### Backup SQLite Database

```bash
# Docker Compose (copy from volume)
docker run --rm -v telegram-content-agent_sqlite_data:/data -v $(pwd):/backup alpine \
  cp /data/style_memory.db /backup/style_memory_$(date +%Y%m%d_%H%M%S).db

# Kubernetes (exec into pod)
kubectl exec -it deployment/telegram-content-agent -- \
  cp /data/style_memory.db /data/style_memory_$(date +%Y%m%d_%H%M%S).db
```

### Restore Database

```bash
# Stop service first
docker-compose stop app

# Restore
docker run --rm -v telegram-content-agent_sqlite_data:/data -v $(pwd):/backup alpine \
  cp /backup/style_memory_20240115_103000.db /data/style_memory.db

# Start service
docker-compose start app
```

### Inspect Database

```bash
# Connect to running container
docker-compose exec app python3 -c "
import aiosqlite, asyncio
async def inspect():
    async with aiosqlite.connect('/data/style_memory.db') as db:
        print('=== Style Memory ===')
        async with db.execute('SELECT * FROM style_memory') as c:
            async for row in c: print(row)
        print('=== Idempotency Keys ===')
        async with db.execute('SELECT fingerprint, status, user_id, created_at FROM idempotency_keys ORDER BY created_at DESC LIMIT 20') as c:
            async for row in c: print(row)
asyncio.run(inspect())
"
```

### Clean Stale Processing Records

```bash
# Automatic cleanup runs periodically, but can be triggered manually
docker-compose exec app python3 -c "
import aiosqlite, asyncio
from datetime import datetime, timedelta, timezone
async def cleanup():
    async with aiosqlite.connect('/data/style_memory.db') as db:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        cursor = await db.execute('DELETE FROM idempotency_keys WHERE status = ? AND updated_at < ?', ('PROCESSING', cutoff))
        await db.commit()
        print(f'Cleaned {cursor.rowcount} stale records')
asyncio.run(cleanup())
"
```

## Google Sheets Operations

### Verify Sheet Access

```bash
docker-compose exec app python3 -c "
import base64, json, gspread
from google.oauth2.service_account import Credentials
import os

creds = json.loads(base64.b64decode(os.environ['GOOGLE_SHEETS_CREDENTIALS_B64']).decode())
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_info(creds, scopes=scopes)
gc = gspread.authorize(credentials)
sh = gc.open_by_key(os.environ['GOOGLE_SHEETS_SPREADSHEET_ID'])
ws = sh.worksheet('Content')
print(f'Rows: {ws.row_count}, Cols: {ws.col_count}')
print(f'Headers: {ws.row_values(1)}')
print(f'Last 5 rows: {ws.get_all_values()[-5:]}')
"
```

### Check Row Count

```bash
docker-compose exec app python3 -c "
import base64, json, gspread
from google.oauth2.service_account import Credentials
import os

creds = json.loads(base64.b64decode(os.environ['GOOGLE_SHEETS_CREDENTIALS_B64']).decode())
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_info(creds, scopes=scopes)
gc = gspread.authorize(credentials)
sh = gc.open_by_key(os.environ['GOOGLE_SHEETS_SPREADSHEET_ID'])
ws = sh.worksheet('Content')
print(f'Total rows (excl header): {ws.row_count - 1}')
"
```

### Export Data

```bash
docker-compose exec app python3 -c "
import base64, json, gspread, csv
from google.oauth2.service_account import Credentials
import os

creds = json.loads(base64.b64decode(os.environ['GOOGLE_SHEETS_CREDENTIALS_B64']).decode())
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = Credentials.from_service_account_info(creds, scopes=scopes)
gc = gspread.authorize(credentials)
sh = gc.open_by_key(os.environ['GOOGLE_SHEETS_SPREADSHEET_ID'])
ws = sh.worksheet('Content')
data = ws.get_all_values()
with open('/data/export.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(data)
print(f'Exported {len(data)} rows to /data/export.csv')
"
```

## LLM Provider Operations

### Check Provider Health

```bash
docker-compose exec app python3 -c "
import asyncio
from app.llm.orchestrator import LLMOrchestrator
from app.memory.service import MemoryService
from app.memory.sqlite_repository import SQLiteRepository

async def check():
    repo = SQLiteRepository('/data/style_memory.db')
    await repo.initialize()
    mem = MemoryService(repo)
    orch = LLMOrchestrator(mem)
    health = await orch.health_check_all()
    print('Provider Health:', health)
    await orch.close()

asyncio.run(check())
"
```

### Test LLM Generation

```bash
docker-compose exec app python3 -c "
import asyncio
from app.ingestion.models import NormalizedContent, ContentType
from app.llm.orchestrator import LLMOrchestrator
from app.memory.service import MemoryService
from app.memory.sqlite_repository import SQLiteRepository

async def test():
    repo = SQLiteRepository('/data/style_memory.db')
    await repo.initialize()
    mem = MemoryService(repo)
    orch = LLMOrchestrator(mem)
    
    content = NormalizedContent(
        content_type=ContentType.TEXT,
        source_identifier='test:manual',
        content='Test content for manual verification',
        content_hash='test_hash',
        user_id=1,
    )
    
    result = await orch.generate(content, 1, 'manual-test')
    print(f'Title: {result.title}')
    print(f'X Post ({len(result.variants.x_post)} chars): {result.variants.x_post}')
    print(f'LinkedIn: {result.variants.linkedin_post[:100]}...')
    
    await orch.close()

asyncio.run(test())
"
```

## Monitoring & Alerting

### Key Metrics to Monitor

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Health check failures | `/health` | >0 failures in 5m |
| Readiness failures | `/ready` | >0 failures in 5m |
| Processing duration | Logs | >60s p95 |
| Error rate | Logs | >5% in 5m |
| LLM fallback rate | Logs | >20% of requests |
| Sheets API errors | Logs | >0 in 5m |
| Duplicate rejection rate | Logs | Sudden spike |
| Database size | Volume | >500MB |

### Prometheus Metrics (if instrumented)

```yaml
# Example alerts
groups:
- name: telegram-content-agent
  rules:
  - alert: HealthCheckFailing
    expr: up{job="telegram-content-agent"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Telegram Content Agent down"
      
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate on Telegram Content Agent"
      
  - alert: LLMFallbackRateHigh
    expr: rate(llm_fallback_total[5m]) / rate(llm_requests_total[5m]) > 0.2
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "High LLM fallback rate"
```

### Log-Based Alerts (grep patterns)

```bash
# Error rate
docker-compose logs app --since 5m | grep -c '"level": "error"'

# LLM fallbacks
docker-compose logs app --since 5m | grep -c "trying next"

# Sheets errors
docker-compose logs app --since 5m | grep -c "SheetsError"

# Processing duration
docker-compose logs app --since 5m | grep "processing_duration" | awk '{print $NF}'
```

## Incident Response

### Bot Not Responding

1. Check container status: `docker-compose ps`
2. Check logs: `docker-compose logs app --tail 100`
3. Verify health: `curl http://localhost:8080/health`
4. Check Telegram token validity
5. Restart if needed: `docker-compose restart app`

### Sheets Write Failures

1. Check service account permissions
2. Verify spreadsheet exists and is shared
3. Check API quotas in Google Cloud Console
4. Verify network connectivity to Google APIs

### High LLM Fallback Rate

1. Check Ollama status: `docker exec ollama ollama ps`
2. Verify Ollama model loaded: `docker exec ollama ollama list`
3. Check Groq/Gemini API keys valid
4. Review provider latency in logs

### Database Issues

1. Check disk space: `df -h /data`
2. Check SQLite integrity: `sqlite3 /data/style_memory.db "PRAGMA integrity_check;"`
3. Check for locks: `lsof /data/style_memory.db`

## Routine Maintenance

### Daily

- [ ] Verify health endpoints responding
- [ ] Check error logs for anomalies
- [ ] Verify Sheets row count increasing as expected

### Weekly

- [ ] Review processing duration trends
- [ ] Check LLM provider fallback rates
- [ ] Verify database backup successful
- [ ] Review disk usage

### Monthly

- [ ] Rotate API keys (Telegram, Groq, Gemini)
- [ ] Update Ollama model if new version
- [ ] Review and cleanup old idempotency records
- [ ] Security scan dependencies: `pip-audit`
- [ ] Update base Docker image

## Scaling Considerations

### Current Limits

- **Long polling**: Single instance handles ~30 msg/sec
- **SQLite**: Single writer, multiple readers OK
- **Sheets API**: 500 requests/100s per project
- **LLM APIs**: Rate limits vary by provider

### Horizontal Scaling

For higher throughput:
1. Multiple bot instances with shared SQLite (requires WAL mode + external locking)
2. Or shard by user_id with separate databases
3. Consider Redis for distributed idempotency
4. Move to PostgreSQL for concurrent writes

### Vertical Scaling

- Increase CPU/Memory for Ollama
- App container: 1-2 CPU, 1-2GB RAM typical

## Disaster Recovery

### RTO/RPO Targets

| Scenario | RTO | RPO |
|----------|-----|-----|
| Container crash | <30s | 0 (SQLite persisted) |
| Host failure | <5m | 0 (volume persisted) |
| Database corruption | <30m | Last backup |
| Region outage | <1h | Last backup |

### Recovery Procedures

1. **Container crash**: Auto-restart via Docker/K8s
2. **Host failure**: Reschedule on new host (volume follows)
3. **Database corruption**: Restore from latest backup
4. **Region outage**: Deploy to secondary region with backup

## Contact & Escalation

| Severity | Response Time | Contact |
|----------|---------------|---------|
| Critical (down) | 15 min | On-call engineer |
| High (degraded) | 1 hour | Team lead |
| Medium (issue) | 4 hours | Team channel |
| Low (question) | Next business day | Documentation |

## Runbook Updates

- Review monthly
- Update after incidents
- Version control in repo