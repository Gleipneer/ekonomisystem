# Household Economics System

Svenskt hushållsekonomisystem — en FastAPI-app med inbäddad
vanilla-JS SPA — för planering, översikt och AI-assisterad
rådgivning kring ett hushålls ekonomi.

## Status

System i drift sedan april 2026. Alla kärn-flöden implementerade och
verifierade. AI-funktioner kräver OpenAI API-nyckel.

| Förmåga | Status |
|---|---|
| CRUD för alla domänentiteter | ✅ |
| Deterministisk sammanfattning + boendekalkyl | ✅ |
| Scenariojämförelse + rapportsnapshots | ✅ |
| Dokumentuppladdning + OCR (swe+eng) | ✅ |
| Data-In AI (klassificering + extraktion) | ✅ |
| Hushållsassistent (read-only analys) | ✅ |
| Bank-PDF export | ✅ |
| Autentisering | ✅ (basic session/token auth) |
| Bankintegration | ❌ |

## Snabbstart

```bash
# Beroenden (Ubuntu)
sudo apt install python3 python3-venv tesseract-ocr tesseract-ocr-swe

# Klona och starta
git clone <repo-url>
cd ekonomisystem
cp .env.example .env    # Redigera: lägg till OPENAI_API_KEY
./scripts/start_app.sh  # Skapar venv, installerar deps, kör migrationer
```

Öppna:
- **Frontend**: http://localhost:8000/
- **API docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/healthz

## Arkitektur

```
FastAPI (app.main:app)
├── REST API (CRUD + workflow)
├── Calculations (deterministisk matematik)
├── AI Services (OpenAI Responses API)
├── Ingest/OCR (Tesseract + text-normalisering)
├── PDF Export (reportlab)
└── Static SPA (vanilla HTML/CSS/JS)
    ↓
SQLite (database.db) + Filesystem (uploaded_files/)
```

Se `docs/ARCHITECTURE.md` för fullständig arkitekturdokumentation.

## Kommandon

| Action | Kommando |
|---|---|
| Installera deps | `source venv/bin/activate && pip install -r requirements.txt` |
| Kör migrationer | `source venv/bin/activate && alembic upgrade head` |
| Kör tester | `source venv/bin/activate && python -m pytest tests/ -v` |
| Starta (dev) | `./scripts/start_app.sh` |
| Health check | `./scripts/healthcheck.sh` |
| Uppdatera/deploy | `./scripts/update-deploy.sh` |
| API docs | http://localhost:8000/docs |

## Dokumentation

| Dokument | Innehåll |
|---|---|
| [`docs/uptodate/README.md`](docs/uptodate/README.md) | Canonical current-state docs (läs först) |
| [`docs/HANDOFF_FOR_OTHER_MODELS.md`](docs/HANDOFF_FOR_OTHER_MODELS.md) | Kondenserad AI-onboarding |
| [`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md) | Kanoniskt sanningsdokument |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Teknisk arkitektur med diagram |
| [`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) | ER-diagram (Mermaid) |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Datamodell och invariants |
| [`docs/AI_CONTRACT.md`](docs/AI_CONTRACT.md) | AI-gränser, prompts, säkerhet |
| [`docs/DEPLOYMENT_UBUNTU.md`](docs/DEPLOYMENT_UBUNTU.md) | Ubuntu-installation |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Drift, start/stopp, felsökning |
| [`docs/ROADMAP_FUTURE.md`](docs/ROADMAP_FUTURE.md) | Framtida förbättringar |
| [`docs/CLEANUP_DECISIONS.md`](docs/CLEANUP_DECISIONS.md) | Cleanup-historik |

## Projektstruktur

```
ekonomisystem/
├── app/
│   ├── main.py           # FastAPI app (routes, workflow)
│   ├── models.py          # SQLAlchemy ORM (17 modeller)
│   ├── schemas.py         # Pydantic v1 schemas
│   ├── calculations.py    # Deterministisk matematik
│   ├── ai_services.py     # OpenAI-integration
│   ├── ingest_content.py  # OCR + text-extraktion
│   ├── pdf_export.py      # Bank-PDF-generering
│   ├── database.py        # Engine + sessions
│   ├── settings.py        # Env-baserad konfiguration
│   └── static/            # SPA (HTML/CSS/JS)
├── alembic/               # Databasmigrationer
├── docs/                  # Dokumentation
├── scripts/
│   ├── start_app.sh       # Lokal start (venv+alembic+port fallback)
│   ├── healthcheck.sh     # Health check
│   ├── update-deploy.sh   # Idempotent deploy
│   └── economic-system.service  # systemd
├── tests/                 # Smoke tests
├── .env.example           # Env-malle
├── Dockerfile             # Container-runtime
├── docker-compose.yml     # Lokal Docker-orkestrering
├── requirements.txt       # Python-beroenden
└── AGENTS.md              # AI-agentregler
```

## Miljövariabler

| Variabel | Default | Beskrivning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./database.db` | Databasanslutning |
| `APP_HOST` | `0.0.0.0` | Host att binda till |
| `APP_PORT` | `8000` | Port |
| `UPLOAD_DIR` | `./uploaded_files` | Uppladdningsmapp |
| `OPENAI_API_KEY` | ej satt | Aktiverar AI-funktioner |
| `OPENAI_MODEL` | `gpt-5.4` | Fallback-modell |
| `OPENAI_ANALYSIS_MODEL` | ej satt | Override för assistent |
| `OPENAI_INGEST_MODEL` | ej satt | Override för ingest |
| `ECON_AI_MODEL_ROUTING_ENABLED` | `true` | Aktiverar assistant-routingpolicy |
| `ECON_AI_DEFAULT_MODEL` | ej satt | Modell för vanlig assistant-chat |
| `ECON_AI_STRUCTURED_MODEL` | ej satt | Modell för structured write-intent/missing-info |
| `ECON_AI_DEEP_ANALYSIS_MODEL` | ej satt | Modell för explicit djupanalys |
| `ECON_AI_FALLBACK_MODEL` | ej satt | Modell för plain-text fallback vid structured schemafel |
| `OPENAI_TIMEOUT_SECONDS` | `45` | AI-timeout |

Autentisering: basic session/token auth är implementerad. Household-assignment/onboarding behöver fortsatt produktpolish.

## Licens

MIT-licens. Fritt att modifiera och anpassa.
