# Historisk onboarding-snapshot. För aktuell status, se docs/uptodate/.
#
# Handoff för andra AI-modeller

Extremt kondenserad onboarding. Läs denna fil först.
Last updated: 2026-04-10.

## Vad är detta?

Svenskt hushållsekonomisystem. En FastAPI-app med inbäddad vanilla-JS SPA.
SQLite-databas, lokal fillagring, valfri OpenAI-integration.

## Läs dessa filer i ordning

1. **`docs/SOURCE_OF_TRUTH.md`** — Vad systemet är, gör, och inte gör
2. **`docs/ARCHITECTURE.md`** — Teknisk arkitektur med diagram
3. **`docs/ER_DIAGRAM.md`** — Datamodell med Mermaid ER
4. **`docs/DATA_MODEL.md`** — Entiteter, relationer, invariants
5. **`docs/AI_CONTRACT.md`** — AI-gränser, prompts, säkerhet
6. **`docs/DEPLOYMENT_UBUNTU.md`** — Installation och serverdrift
7. **`docs/OPERATIONS.md`** — Drift, start/stopp, felsökning
8. **`docs/ROADMAP_FUTURE.md`** — Framtida förbättringar
9. **`AGENTS.md`** — Regler för AI-agenter som arbetar i repot
10. **`app/main.py`** — All route-logik (stort men en fil)
11. **`app/models.py`** — Alla ORM-modeller

## Viktigaste invariants

1. AI skriver ALDRIG tyst till kanoniska tabeller
2. Backend äger all finansmatematik
3. Data-In: analyze → promote → apply (tre separata steg)
4. Promote skapar bara workflow-artefakter (Document + ExtractionDraft)
5. Pydantic v1 (`.dict()`, INTE `.model_dump()`)
6. SQLite-first, allt i en process

## Viktigaste kommandon

```bash
source venv/bin/activate && pip install -r requirements.txt  # deps
source venv/bin/activate && alembic upgrade head              # migrationer
source venv/bin/activate && python -m pytest tests/ -v        # tester
./scripts/start_app.sh                                        # starta
curl http://localhost:8000/healthz                             # health check
```

## Viktigaste beslut

- Pydantic v1, inte v2
- SQLite utan extern databas
- Ingen autentisering (trust = Tailscale/localhost)
- OpenAI via Responses API, ingen provider-abstraktion
- Frontend är vanilla JS (ingen React/Vue)
- Alla routes i en fil (`main.py`, ~2400 rader)
- 9 AI-klassificeringstyper, se `docs/AI_CONTRACT.md`

## Vad som fortfarande är osäkert

- Historisk `502` på subscription-submit via mobil/Tailscale — ej reproducerad lokalt
- `app.js` innehåller blandat legacy + aktivt — redigera försiktigt
- Dubblettkontroll mot kanonisk data (bara mot drafts idag)
- Evidenskedja (document → draft → applied entity) — implicit, ej explicit

## Arkitektonisk skuld att vara medveten om

- `main.py` bör brytas ut till routers (men fungerar idag)
- `app.js` bör rensas på död legacy-kod
- `AUTO_CREATE_SCHEMA=true` kan maskera migrationsproblem
