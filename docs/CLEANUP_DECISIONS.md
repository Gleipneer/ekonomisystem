# Cleanup-beslut

Dokumenterar vad som rensats, arkiverats eller ändrats, och varför.
Date: 2026-04-10.

## Raderade filer

### `browser-subscription.txt` → RADERAD
- **Evidens**: Testdata (klistrad Spotify-abonnemangstext) i repo-roten
- **Motivering**: Hör inte hemma i repo-roten, ingen kod refererar till den

### `household_economics.db` → RADERAD
- **Evidens**: 0-byte tom fil bredvid den faktiska `database.db`
- **Motivering**: Överbliven, skapar förvirring om vilken DB som är aktiv

### `.run/tailscale-start.log` → RADERAD
- **Evidens**: Stale log-fil i IDE-specifik mapp
- **Motivering**: Bör inte vara i repo, genererad runtime-data

### `app/static/system_validation.md` → RADERAD
- **Evidens**: Pekare till `docs/SYSTEM_VALIDATION.md`, servades aldrig
- **Motivering**: Redundant, direkt reference till docs/ räcker

## Arkiverade/komprimerade dokument

### Docs som ersatts av ny dokumentationsryggrad

Följande filer under `docs/` har ersatts av nya kanoniska dokument men
behålls tills vidare med "Legacy Pointer"-noteringar som de redan hade,
eftersom de inte skapar aktivt brus:

| Gammal fil | Ersatt av |
|---|---|
| `docs/architecture.md` | `docs/ARCHITECTURE.md` (ny version) |
| `docs/frontend_handover.md` | `docs/HANDOFF_FOR_OTHER_MODELS.md` |
| `docs/master_roadmap.md` | `docs/ROADMAP_FUTURE.md` |
| `docs/runbook.md` | `docs/OPERATIONS.md` |

### Docs som konsoliderats

| Gammal fil | Status | Handling |
|---|---|---|
| `docs/HANDOFF_MASTER.md` | Ersatt av `HANDOFF_FOR_OTHER_MODELS.md` | Behålls som redirect |
| `docs/CURRENT_STATE.md` | Info nu i `SOURCE_OF_TRUTH.md` + `ARCHITECTURE.md` | Behålls, fortf. värdefullt |
| `docs/LOCKED_DECISIONS.md` | Info nu i `SOURCE_OF_TRUTH.md` | Behålls, fortf. värdefullt |
| `docs/FRONTEND_DIRECTION.md` | Behålls som-is | Unik frontend-guidning |
| `docs/AI_DIRECTION.md` | Ersatt av `AI_CONTRACT.md` | Behålls som referens |
| `docs/KNOWN_GAPS_AND_RISKS.md` | Info delvis i `SOURCE_OF_TRUTH.md` | Behålls |
| `docs/RUNTIME_AND_OPERATIONS.md` | Ersatt av `OPERATIONS.md` + `DEPLOYMENT_UBUNTU.md` | Behålls som referens |
| `docs/PROJECT_CONTEXT.md` | Info nu i `SOURCE_OF_TRUTH.md` | Behålls |
| `docs/REPO_MAP.md` | Info nu i `ARCHITECTURE.md` | Behålls |
| `docs/TERMS_AND_MODEL.md` | Info nu i `DATA_MODEL.md` | Behålls |

### "Patch"-docs som nu är historik

| Fil | Status |
|---|---|
| `docs/AINEXTSTEPPATCH.md` | Patch mestadels implementerad (bank-paste funkar) |
| `docs/INTELLIGENCE_LAYER_PATCH_V1.md` | Patch komplett och verifierad |
| `docs/INGEST_AND_INTELLIGENCE_ROADMAP.md` | Delvis implementerad, delvis i ROADMAP_FUTURE |
| `docs/NEXT_ACTION.md` | Nästa uppgift uppdaterad i kontext |
| `docs/SYSTEM_VALIDATION.md` | Info nu i OPERATIONS.md |

Dessa behålls som historisk referens men är inte del av den kanoniska
dokumentationsryggraden.

## Root-level cleanup

### `READMEAI.md` → BEHÅLLS
- **Motivering**: Innehåller specifik verifieringsinformation från saneringpass.
  Skapar minimal brus. Kan arkiveras i framtiden.

### `AI_START_HERE.md` → UPPDATERAS
- **Motivering**: Pekar om till nya kanoniska docs istället för gamla.

## Kod-cleanup (inga brytande ändringar)

### `app/static/server.py` → BEHÅLLS (markerad)
- **Motivering**: Inte primary runtime, men raderas inte — kan användas för
  minimalistisk frontend-only-test. Redan markerad som non-primary i docs.

### `app/system_docs.py` → BEHÅLLS (markerad)
- **Motivering**: Serveras via `/system/validation_markdown`. Låg risk att behålla.

## Dockerfile → UPPDATERAD
- **Ändring**: Lade till `tesseract-ocr`, `tesseract-ocr-swe`, `curl`, healthcheck, alembic migration
- **Motivering**: OCR fungerade inte i Docker, ingen healthcheck, migrationer kördes inte

## Nya filer skapade

| Fil | Syfte |
|---|---|
| `docs/SOURCE_OF_TRUTH.md` | Kanoniskt sanningsdokument |
| `docs/ARCHITECTURE.md` | Ny version med Mermaid-diagram |
| `docs/ER_DIAGRAM.md` | Mermaid ER + modellbeskrivning |
| `docs/DATA_MODEL.md` | Entiteter, invariants, normaliseringsflöden |
| `docs/AI_CONTRACT.md` | AI-gränser, prompts, säkerhet |
| `docs/DEPLOYMENT_UBUNTU.md` | Ubuntu deployment-guide |
| `docs/OPERATIONS.md` | Drift, start/stopp, felsökning |
| `docs/HANDOFF_FOR_OTHER_MODELS.md` | Kondenserad AI-onboarding |
| `docs/ROADMAP_FUTURE.md` | Framtida förbättringar |
| `docs/CLEANUP_DECISIONS.md` | Denna fil |
| `scripts/economic-system.service` | systemd service-fil |
| `scripts/healthcheck.sh` | Health check script |
| `scripts/update-deploy.sh` | Idempotent update/deploy script |
