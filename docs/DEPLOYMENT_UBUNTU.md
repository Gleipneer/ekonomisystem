# Deployment på Ubuntu

Steg-för-steg-guide för att köra systemet på en Ubuntu-server.
Last verified: 2026-04-14.

## Systemkrav

| Komponent | Krav |
|---|---|
| OS | Ubuntu 22.04+ |
| Python | 3.11+ |
| Disk | ~500MB (app + venv + SQLite) |
| RAM | ~256MB (uvicorn + SQLite) |
| Nätverk | Tailscale rekommenderas |
| Extern | OpenAI API-nyckel (valfritt, för AI-funktioner) |

## Systemberoenden

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
    tesseract-ocr tesseract-ocr-swe
```

## Installation

```bash
# Klona repot
git clone <repo-url> /opt/economic_system
cd /opt/economic_system

# Skapa .env
cp .env.example .env
# Redigera .env — sätt OPENAI_API_KEY om AI-funktioner önskas

# Starta (skapar venv, installerar deps, kör migrationer)
./scripts/start_app.sh
```

## Env-konfiguration

Redigera `/opt/economic_system/.env`:

```bash
DATABASE_URL=sqlite:///./database.db
APP_HOST=0.0.0.0
APP_PORT=8000
UPLOAD_DIR=./uploaded_files
CORS_ALLOW_ORIGINS=*
AUTO_CREATE_SCHEMA=true

# Valfritt — AI-funktioner
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4
OPENAI_ANALYSIS_MODEL=gpt-5.4-mini
OPENAI_INGEST_MODEL=gpt-5.4-mini
ECON_AI_MODEL_ROUTING_ENABLED=true
ECON_AI_DEFAULT_MODEL=
ECON_AI_STRUCTURED_MODEL=
ECON_AI_DEEP_ANALYSIS_MODEL=
ECON_AI_FALLBACK_MODEL=
OPENAI_TIMEOUT_SECONDS=45
```

## systemd-tjänst

Kopiera servicefilen:

```bash
sudo cp scripts/economic-system.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable economic-system
sudo systemctl start economic-system
```

Verifiera:
```bash
sudo systemctl status economic-system
curl http://localhost:8000/healthz
```

## Uppdatera systemet

```bash
cd /opt/economic_system
./scripts/update-deploy.sh
```

Scriptet gör:
1. `git pull`
2. Installerar nya deps
3. Kör `alembic upgrade head`
4. Startar om tjänsten

## Tailscale-åtkomst

Om servern kör Tailscale och appen binder till `0.0.0.0`:

```bash
# Hämta serverns Tailscale-IP
tailscale ip -4

# Appen nås på:
# http://<tailscale-ip>:8000/
```

För att exponera via Tailscale Funnel (publik access):
```bash
tailscale funnel 8000
```

Viktigt:
- Appen har egen session-baserad auth. Oautentiserade användare ska mötas av inloggningsläget innan någon hushållsdata exponeras.
- Startscriptet skriver både lokal URL och Tailscale-IP vid start. Verifiera dem efter varje omstart.
- Funnel är rimligt först när minst en riktig användare finns registrerad och `BYPASS_AUTH` inte används.

## Reverse proxy (valfritt)

Om du vill köra bakom nginx med HTTPS:

```nginx
server {
    listen 443 ssl;
    server_name ekonomi.example.com;

    ssl_certificate /etc/letsencrypt/live/ekonomi.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ekonomi.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
    }
}
```

## Docker (alternativ)

```bash
docker-compose up -d --build
```

> **OBS**: Dockerfilen installerar Tesseract för OCR-stöd.
> Databas och uppladdade filer lagras i bind-mountade volymer.

## Backup

Minsta backup — kopiera dessa:
```bash
cp database.db database.db.backup.$(date +%Y%m%d)
cp -r uploaded_files/ uploaded_files.backup.$(date +%Y%m%d)/
cp .env .env.backup
```

Automatisk daglig backup via cron:
```bash
# Lägg till i crontab -e
0 3 * * * cd /opt/economic_system && cp database.db backups/database.db.$(date +\%Y\%m\%d) 2>/dev/null
```
