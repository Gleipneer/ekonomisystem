# docs/uptodate - canonical current state

## Titel
Canonical current-state dokumentation for `ekonomisystem`

**Senast verifierad:** 2026-04-28  
**Status:** Aktiv, avsedd som primär källa för beslut  
**Källa/grund:** `app/main.py`, `app/ai_services.py`, `app/schemas.py`, `app/models.py`, testfiler och runtime-checkar i detta pass

Denna mapp innehåller endast aktuell och verifierad information. Om äldre dokument i `docs/` säger något annat ska `docs/uptodate/` gälla tills motsatsen verifierats i kod/test.

## Dokumentindex

- `SYSTEM_BLUEPRINT.md` - Systemöversikt, sanningsgränser och domänmodell.
- `FRONTEND_TEAM_BRIEF.md` - Kontrakt och arbetssätt för GUI-team (inkl. state machines och testscenarier).
- `API_CONTRACT_FOR_FRONTEND.md` - Frontendrelevanta API-kontrakt baserat på faktiska routes.
- `AI_CONTRACT_CURRENT.md` - Aktuell AI-arkitektur, strict schema-fix, fallback och apply-säkerhet.
- `DATA_IN_PROVENANCE.md` - Analyze/promote/apply med serverägd provenance och hash-skydd.
- `RUNTIME_AND_TESTING.md` - Drift, verifieringskommandon, smoke-flöden och senaste testutfall.
- `KNOWN_LIMITATIONS_AND_NEXT_STEPS.md` - Endast aktuella risker och prioriterade nästa steg.

## Tolkningsregel

- Använd denna mapp först.
- Använd äldre docs som historik, inte som primär sanning.
- Vid konflikt: verifiera mot kod (`app/*.py`) och tester (`tests/`).
