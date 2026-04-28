# System Blueprint

## Titel
System blueprint - backend truth boundary och GUI-samarbete

**Senast verifierad:** 2026-04-28  
**Status:** Aktiv  
**Källa/grund:** `app/main.py`, `app/ai_services.py`, `app/schemas.py`, `app/models.py`

## Verifierad fakta

- Systemet är en självhostad svensk hushållsekonomiapp med FastAPI-backend.
- Datalager är SQLite-first (`DATABASE_URL` default `sqlite:///./database.db`).
- Frontend är inbäddad SPA i backend (`/` serverar statisk klient).
- Domänområden i API: hushåll, personer, inkomster, återkommande kostnader, abonnemang, lån/skulder, försäkringar, tillgångar, fordon, dokument, drafts, analyser, scenarier, rapportsnapshots.
- Backend beräknar ekonomi deterministiskt (`/households/{id}/analysis` och `/analysis/cycle`), inte frontend.

## Designkontrakt

### Sanningsgräns

- **Kanonisk data**: tabeller för ekonomiobjekt (`recurring_costs`, `subscription_contracts`, `loans`, `income_sources`, m.fl.).
- **Workflow-artefakter**: `documents`, `extraction_drafts`, `ingest_analysis_results`, chatthistorik.
- **AI-ytor** returnerar tolkning/förslag men ska inte skriva kanonisk data i samma steg.

### Fakta vs förslag

- **Fakta:** läsning från kanoniska tabeller och deterministiska analyssvar.
- **Förslag:** `write_intent` från assistant och `suggestions` från ingest analyze.
- **Analys:** deterministic analysis endpoints + AI-förklaringar.
- **Advisory:** kan exponeras i analyssvar men ersätter inte kanonisk data.
- **Kanonisk skrivning:** kräver explicit apply-steg i backend.

### AI:s roll

- AI är tolk/förslagsmotor/förklarare.
- AI är inte sanningskälla och får inte kringgå apply-grindar.
- `assistant/respond` producerar svar + ev. `write_intent` men inte kanonisk write.

### Interna överföringar

- Interna överföringar (ex. räkningskonto/matkonto/huskonto) ska behandlas separat från konsumtionskostnad tills tydlig regel/klassning finns.
- UI och rapportering ska kunna visa "transfer/saving candidate" separat från utgift.

## Osäkerheter/kvarvarande risker

- Delar av analyspaketet refereras från `app.main`/`app.ai_services` men motsvarande källfiler saknas i nuvarande tracked tree (endast bytecode finns lokalt); detta ökar förvaltningsrisk och gör full källgranskning svårare.
- `app/main.py`, `app/ai_services.py` och `app/static/app.js` är stora hotspots för vidare modularisering.
