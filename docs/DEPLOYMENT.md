# Deployment Guide

This guide covers deploying the Telegram Content Agent to various platforms.

## Prerequisites

- Docker and docker-compose installed
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Google Cloud Project with Sheets API enabled
- Google Service Account with Sheets access
- (Optional) Groq API key from [console.groq.com](https://console.groq.com)
- (Optional) Gemini API key from [aistudio.google.com](https://aistudio.google.com)

## Google Cloud Setup

### 1. Create Google Cloud Project

```bash
gcloud projects create YOUR_PROJECT_ID
gcloud config set project YOUR_PROJECT_ID
```

### 2. Enable APIs

```bash
gcloud services enable sheets.googleapis.com drive.googleapis.com
```

### 3. Create Service Account

```bash
gcloud iam service-accounts create telegram-content-agent \
    --display-name="Telegram Content Agent"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:telegram-content-agent@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/editor"
```

### 4. Create and Download Key

```bash
gcloud iam service-accounts keys create credentials.json \
    --iam-account=telegram-content-agent@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 5. Encode Credentials

```bash
cat credentials.json | base64 -w 0
# Copy output to GOOGLE_SHEETS_CREDENTIALS_B64
```

### 6. Create Spreadsheet

1. Create a Google Spreadsheet
2. Share with the service account email (Editor access)
3. Copy Spreadsheet ID from URL: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

Required:
- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_SHEETS_CREDENTIALS_B64`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

Optional (for cloud LLM fallback):
- `GROQ_API_KEY`
- `GEMINI_API_KEY`

## Local Development

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env
python -m app.main
```

## Docker Deployment

### Build and Run

```bash
docker-compose up --build -d
```

### View Logs

```bash
docker-compose logs -f app
```

### Stop

```bash
docker-compose down
```

### Stop and Remove Volumes

```bash
docker-compose down -v
```

### Pull Ollama Model (if using Ollama)

```bash
docker exec -it telegram-content-agent-ollama ollama pull llama3.1
```

## Platform-Specific Deployment

### Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Launch (creates fly.toml)
fly launch --no-deploy

# Set secrets
fly secrets set \
  TELEGRAM_BOT_TOKEN=... \
  GOOGLE_SHEETS_CREDENTIALS_B64=... \
  GOOGLE_SHEETS_SPREADSHEET_ID=... \
  GROQ_API_KEY=... \
  GEMINI_API_KEY=...

# Deploy
fly deploy
```

**fly.toml example:**

```toml
app = "telegram-content-agent"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  HEALTH_HOST = "0.0.0.0"
  HEALTH_PORT = "8080"
  DATABASE_PATH = "/data/style_memory.db"
  LLM_PRIMARY_PROVIDER = "groq"
  LLM_FALLBACK_PROVIDERS = "gemini"

[mounts]
  source = "sqlite_data"
  destination = "/data"

[[services]]
  http_checks = []
  internal_port = 8080
  processes = ["app"]
  protocol = "tcp"
  script_checks = []
  [services.concurrency]
    hard_limit = 25
    soft_limit = 20
  [[services.ports]]
    handlers = ["http"]
    port = 8080
  [[services.tcp_checks]]
    grace_period = "1s"
    interval = "15s"
    restart_limit = 0
    timeout = "2s"
```

### Railway

1. Connect GitHub repository
2. Add environment variables in dashboard
3. Deploy (uses Dockerfile automatically)

### Render

1. Create new Web Service
2. Connect repository
3. Set build command: `docker build -t app .`
4. Set start command: `docker run -p 8080:8080 app`
5. Add environment variables

### AWS ECS (Fargate)

```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker build -t telegram-content-agent .
docker tag telegram-content-agent:latest ACCOUNT.dkr.ecr.us-east.1.amazonaws.com/telegram-content-agent:latest
docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/telegram-content-agent:latest
```

**Task Definition (JSON):**

```json
{
  "family": "telegram-content-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/telegram-content-agent:latest",
      "portMappings": [{"containerPort": 8080, "protocol": "tcp"}],
      "environment": [
        {"name": "HEALTH_HOST", "value": "0.0.0.0"},
        {"name": "HEALTH_PORT", "value": "8080"},
        {"name": "DATABASE_PATH", "value": "/data/style_memory.db"},
        {"name": "LLM_PRIMARY_PROVIDER", "value": "groq"},
        {"name": "LLM_FALLBACK_PROVIDERS", "value": "gemini"}
      ],
      "secrets": [
        {"name": "TELEGRAM_BOT_TOKEN", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "GOOGLE_SHEETS_CREDENTIALS_B64", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "GOOGLE_SHEETS_SPREADSHEET_ID", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "GROQ_API_KEY", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "GEMINI_API_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "mountPoints": [
        {"sourceVolume": "sqlite_data", "containerPath": "/data"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/telegram-content-agent",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 15
      }
    }
  ],
  "volumes": [
    {
      "name": "sqlite_data",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-XXXXXXXX",
        "rootDirectory": "/telegram-content-agent"
      }
    }
  ]
}
```

### Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/telegram-content-agent

# Deploy
gcloud run deploy telegram-content-agent \
  --image gcr.io/PROJECT_ID/telegram-content-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars HEALTH_HOST=0.0.0.0,HEALTH_PORT=8080,DATABASE_PATH=/data/style_memory.db,LLM_PRIMARY_PROVIDER=groq,LLM_FALLBACK_PROVIDERS=gemini \
  --set-secrets TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,GOOGLE_SHEETS_CREDENTIALS_B64=sheets-credentials:latest,GOOGLE_SHEETS_SPREADSHEET_ID=sheets-id:latest,GROQ_API_KEY=groq-key:latest,GEMINI_API_KEY=gemini-key:latest \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10
```

**Note:** Cloud Run uses HTTP-based scaling. Since we use long polling, set `--min-instances 1` to keep the bot connection alive, or use a separate always-on service.

### Kubernetes

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: telegram-content-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: telegram-content-agent
  template:
    metadata:
      labels:
        app: telegram-content-agent
    spec:
      containers:
      - name: app
        image: telegram-content-agent:latest
        ports:
        - containerPort: 8080
        env:
        - name: HEALTH_HOST
          value: "0.0.0.0"
        - name: HEALTH_PORT
          value: "8080"
        - name: DATABASE_PATH
          value: "/data/style_memory.db"
        - name: LLM_PRIMARY_PROVIDER
          value: "groq"
        - name: LLM_FALLBACK_PROVIDERS
          value: "gemini"
        envFrom:
        - secretRef:
            name: telegram-content-agent-secrets
        volumeMounts:
        - name: sqlite-data
          mountPath: /data
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
      volumes:
      - name: sqlite-data
        persistentVolumeClaim:
          claimName: sqlite-pvc
---
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: sqlite-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: telegram-content-agent-secrets
type: Opaque
stringData:
  TELEGRAM_BOT_TOKEN: "your-token"
  GOOGLE_SHEETS_CREDENTIALS_B64: "base64-credentials"
  GOOGLE_SHEETS_SPREADSHEET_ID: "spreadsheet-id"
  GROQ_API_KEY: "groq-key"
  GEMINI_API_KEY: "gemini-key"
```

## Resource Requirements

| Component | CPU | Memory | Disk |
|-----------|-----|--------|------|
| App | 0.5-1 core | 512MB-1GB | 100MB |
| Ollama (llama3.1) | 2-4 cores | 8-16GB | 5-10GB |
| SQLite | Minimal | Minimal | <100MB |

**Recommendation:** For free tiers, omit Ollama and use Groq/Gemini as primary.

## Health Checks

```bash
# Liveness
curl http://localhost:8080/health
# {"status": "healthy", "service": "telegram-content-agent"}

# Readiness
curl http://localhost:8080/ready
# {"status": "ready", "checks": {"database": "ok", "sheets": "ok", "llm_providers": {...}}}
```

## Troubleshooting Deployment

| Issue | Solution |
|-------|----------|
| Bot not responding | Check logs: `docker-compose logs app` |
| Sheets permission denied | Verify service account has Editor access to spreadsheet |
| Ollama model not found | Run: `docker exec ollama ollama pull llama3.1` |
| Health check fails | Verify `/health` endpoint responds, check container logs |
| Database locked | Ensure only one container mounts the volume |

## Production Checklist

- [ ] Strong `TELEGRAM_BOT_TOKEN`
- [ ] Service Account with minimal permissions (Sheets + Drive)
- [ ] Spreadsheet shared with service account email only
- [ ] `GROQ_API_KEY` and/or `GEMINI_API_KEY` for fallback
- [ ] Ollama model pulled (if using Ollama)
- [ ] Log aggregation configured
- [ ] Monitoring on `/health` and `/ready`
- [ ] Alerts on error rates
- [ ] Volume backup/restore tested
- [ ] Resource limits set appropriately