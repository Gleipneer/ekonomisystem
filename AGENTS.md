# AGENTS.md

## Instruktioner för AI-agenter

### Översikt

**Household Economics System** — en FastAPI-monolith med inbäddad vanilla HTML/CSS/JS frontend.
SQLite som standard, ingen extern databas. Se `docs/HANDOFF_FOR_OTHER_MODELS.md` för snabb onboarding.

### Läsordning

1. `docs/HANDOFF_FOR_OTHER_MODELS.md` — Kondenserad onboarding
2. `docs/SOURCE_OF_TRUTH.md` — Kanoniskt sanningsdokument
3. `docs/ARCHITECTURE.md` — Teknisk arkitektur
4. `docs/ER_DIAGRAM.md` — Datamodell (ER)
5. `docs/DATA_MODEL.md` — Datamodell och invariants
6. `docs/AI_CONTRACT.md` — AI-gränser och kontrakt
7. `docs/DEPLOYMENT_UBUNTU.md` — Ubuntu-installation
8. `docs/OPERATIONS.md` — Drift och felsökning
9. `docs/ROADMAP_FUTURE.md` — Framtida förbättringar
10. `AGENTS.md` — Denna fil

### Snabbreferens

| Action | Kommando |
|---|---|
| Installera deps | `source venv/bin/activate && pip install -r requirements.txt` |
| Kör migrationer | `source venv/bin/activate && alembic upgrade head` |
| Kör tester | `source venv/bin/activate && python -m pytest tests/ -v` |
| Starta dev | `source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| API docs | `http://localhost:8000/docs` |
| Frontend UI | `http://localhost:8000/` |
| Health check | `curl http://localhost:8000/healthz` |

### Icke-uppenbara regler

- **Pydantic v1** (1.10.9). Använd `.dict()` inte `.model_dump()`, och `class Config` inte `model_config`.
- `.env` läses via `python-dotenv`. Kopiera `.env.example` till `.env` före första körning.
- `OPENAI_API_KEY` är valfri. AI-routes returnerar `503` graciöst utan den.
- SQLite-DB på `./database.db`. Radera → `alembic upgrade head` återskapar.
- `scripts/start_app.sh` hittar automatiskt ledig port om 8000 är upptagen.
- `AUTO_CREATE_SCHEMA=true` kör `create_all()` på startup, men Alembic är migrationsvägen.
- Tester i `tests/test_smoke.py` använder `importlib.reload` — kolla `get_settings.cache_clear()` vid env-byte.

### AI-invariants (FÅR INTE BRYTAS)

1. **AI skriver ALDRIG tyst till kanoniska tabeller.** analyze → promote → apply, tre separata steg.
2. **Backend äger all finansmatematik.** Inga beräkningar i frontend eller AI.
3. **Promote skapar bara workflow-artefakter** (Document + ExtractionDraft).
4. **Saknar API-nyckel → 503**, aldrig fejkade svar.
5. **Determinism framför magi.** Förutsägbar, reproducerbar logik.

### Datamodell (nyckelentiteter)

9 klassificeringstyper: `subscription_contract`, `invoice`, `recurring_cost_candidate`, `transfer_or_saving_candidate`, `bank_row_batch`, `insurance_policy`, `loan_or_credit`, `financial_note`, `unclear`.

17 tabeller. Se `docs/ER_DIAGRAM.md` för fullständigt diagram.

### Token-/kostnadsmedvetenhet

- Analys-assistent: ~650-1000 tokens per anrop
- Enkel ingest: ~1600-1900 tokens
- Bank-paste batch: ~2400-2500 tokens
- OCR: kräver `tesseract-ocr` + `tesseract-ocr-swe` (systempaket)

### Arbetsprinciper

1. **Sanning först.** Dokumentationen speglar koden, aldrig tvärtom.
2. **Minsta möjliga ändring.** Gör inte mer än det som krävs.
3. **Verifieringsdisciplin.** Kör tester efter alla ändringar.
4. **Dokumentationsplikt.** Uppdatera docs vid alla signifikanta ändringar.
5. **Rensa inte aggressivt.** Dokumentera varför om du tar bort något.
6. **Använd `merge` när det passar bäst.** Vid större repoanalys/review, låt `merge` ge hotspots/sammanfattning först och komplettera med riktad kodläsning.
