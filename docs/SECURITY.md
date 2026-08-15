# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest release | ✅ |
| Previous minor | ⚠️ Security fixes only |
| Older | ❌ |

## Reporting a Vulnerability

**Do not report security vulnerabilities via public GitHub issues.**

Instead, email: **security@your-org.com** (or create a private security advisory on GitHub)

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will:
- Acknowledge within 48 hours
- Provide initial assessment within 7 days
- Keep you informed of progress
- Credit you in the fix (if desired)

## Security Features

### Input Validation & Sanitization

| Vector | Protection |
|--------|------------|
| Telegram messages | Size limits, type validation |
| URLs | Scheme validation (http/https only), SSRF protection |
| PDF uploads | MIME type check, magic bytes verification, size limits |
| Style prompts | Length limit (2000 chars), sanitization |
| File paths | Path traversal prevention, sanitization |

### Secret Management

- **No secrets in code** - All via environment variables
- **Base64-encoded credentials** - Google service account JSON never written to disk
- **Structured logging** - No API keys, tokens, or sensitive data in logs
- **Container non-root** - Runs as `appuser` (UID 1000)

### Network Security

| Component | Protection |
|-----------|------------|
| Outbound HTTP | Timeouts, redirect limits, realistic User-Agent |
| URL fetching | SSRF protection (blocks localhost, private IPs, .local domains) |
| Telegram | Long polling (no inbound ports exposed) |
| Health checks | Internal only (not exposed externally by default) |
| Google Sheets | Service account with minimal permissions |

### Data Protection

| Data | At Rest | In Transit |
|------|---------|------------|
| User styles | SQLite (volume) | N/A (local) |
| Idempotency keys | SQLite (volume) | N/A (local) |
| Google Sheets | Google Cloud (encrypted) | TLS 1.2+ |
| LLM prompts | N/A | TLS 1.2+ (HTTPS) |
| Telegram messages | N/A | TLS 1.2+ (Telegram API) |

## Threat Model

### Assets

1. **User style preferences** - Low sensitivity
2. **Content submissions** - User-provided, may be sensitive
3. **Google Sheets data** - Business content
4. **Service account credentials** - High sensitivity
5. **LLM API keys** - Medium sensitivity

### Threat Actors

| Actor | Capability | Motivation |
|-------|------------|------------|
| External attacker | Network access, bot token | Data theft, spam, disruption |
| Malicious user | Bot access | Prompt injection, resource exhaustion |
| Insider | Source access | Credential theft |
| Compromised dependency | Supply chain | Code execution |

### Attack Vectors & Mitigations

| Vector | Likelihood | Impact | Mitigation |
|--------|------------|--------|------------|
| Prompt injection | Medium | Medium | System prompt isolation, untrusted content marking |
| SSRF via URL | Low | High | Scheme validation, private IP blocking |
| Path traversal | Low | Medium | Filename sanitization, no user-controlled paths |
| Resource exhaustion | Medium | Medium | Size limits, timeouts, rate limits |
| SQL injection | Low | High | Parameterized queries only |
| Credential leakage | Low | Critical | Base64 env vars, no logging, non-root container |
| Supply chain | Low | Critical | Pinned dependencies, pip-audit |

## Secure Configuration

### Required for Production

```env
# .env - Production values
TELEGRAM_BOT_TOKEN=*****  # Strong token from BotFather
GOOGLE_SHEETS_CREDENTIALS_B64=*****  # Base64 service account
GOOGLE_SHEETS_SPREADSHEET_ID=*****  # Specific spreadsheet
GROQ_API_KEY=*****  # If using Groq
GEMINI_API_KEY=*****  # If using Gemini

# Security hardening
MAX_TEXT_LENGTH=50000
MAX_PDF_SIZE_MB=50
MAX_URL_CONTENT_LENGTH=100000
MAX_STYLE_LENGTH=2000
HTTP_TIMEOUT_SECONDS=30
LLM_TIMEOUT_SECONDS=120
```

### Service Account Permissions

Minimal IAM roles for Google Service Account:

```bash
# Only Sheets and Drive access needed
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:bot@project.iam.gserviceaccount.com" \
  --role="roles/spreadsheets.editor"

# Or custom role with minimal permissions:
# - spreadsheets.spreadsheets.update
# - spreadsheets.values.update
# - spreadsheets.values.append
# - drive.files.get (for spreadsheet access)
```

### Network Policies (Kubernetes)

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: telegram-content-agent
spec:
  podSelector:
    matchLabels:
      app: telegram-content-agent
  policyTypes:
  - Egress
  egress:
  - to: []  # Allow all egress for Telegram, Google, LLM APIs
    ports:
    - protocol: TCP
      port: 443  # HTTPS
    - protocol: TCP
      port: 80   # HTTP (if any)
  - to:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 8080  # Health checks
```

## Dependency Security

### Scanning

```bash
# Install pip-audit
pip install pip-audit

# Scan dependencies
pip-audit -r requirements.txt

# With GitHub Advisory Database
pip-audit -r requirements.txt --vulnerability-db github
```

### Update Policy

- **Security updates**: Apply within 48 hours
- **Minor updates**: Test and apply within 1 week
- **Major updates**: Plan migration, test thoroughly

### Pinned Dependencies

```txt
# requirements.txt - All versions pinned
python-telegram-bot==21.4
pydantic==2.10.6
pydantic-settings==2.10.1
httpx==0.27.2
ollama==0.4.2
groq==0.13.0
google-generativeai==0.8.0
gspread==6.2.0
google-auth==2.33.0
trafilatura==1.9.0
markitdown==0.1.0
aiosqlite==0.20.0
python-dotenv==1.0.1
structlog==24.1.0
tenacity==8.5.0
```

## Incident Response

### If Compromised

1. **Immediate**: Revoke compromised credentials
   - Rotate Telegram bot token: `/revoke` in BotFather
   - Rotate Google service account key
   - Rotate Groq/Gemini API keys

2. **Contain**: Stop affected containers
   ```bash
   docker-compose down
   ```

3. **Assess**: Check logs for unauthorized access
   ```bash
   docker-compose logs app | grep -i "unauthorized\|forbidden\|error"
   ```

4. **Recover**: Deploy clean version with new credentials

5. **Notify**: Inform affected users if data exposed

### Post-Incident

- Root cause analysis
- Update threat model
- Improve detection/prevention
- Document lessons learned

## Compliance Considerations

### Data Processing

- **GDPR**: User styles = personal data (user_id + preference)
  - Right to deletion: `/clearstyle` command
  - Data minimization: Only store user_id + style
  - Retention: Until user clears or admin purges

- **No PII in Sheets**: Content submissions may contain user data
  - Consider anonymization if required

### Audit Logging

```bash
# Enable audit logging for sensitive operations
# In production, forward to SIEM
docker-compose logs app | jq 'select(.event | contains("style") or contains("delete"))'
```

## Security Checklist for Deployments

- [ ] All secrets in environment variables (not code)
- [ ] Service account has minimal permissions
- [ ] Spreadsheet shared only with service account
- [ ] Non-root container user
- [ ] Resource limits set (CPU, memory)
- [ ] Health checks configured
- [ ] Log aggregation configured
- [ ] Monitoring alerts configured
- [ ] Backup strategy tested
- [ ] Dependency scan passes
- [ ] Network policies applied (if K8s)
- [ ] TLS for all external connections
- [ ] Rate limiting considered (if public bot)

## Contact

Security Team: **security@your-org.com**

PGP Key: Available on request

## Updates

This policy is reviewed quarterly. Last updated: 2024-01-15