# Runtime and Testing

## Titel
Runtime, verifiering och säker smoke

**Senast verifierad:** 2026-04-28
**Status:** Verifierad i detta pass
**Källa/grund:** `AGENTS.md`, kommandon körda i detta pass, runtime-checkar

## Start enligt repo-standard

- Installera deps: `source venv/bin/activate && pip install -r requirements.txt`
- Migrationer: `source venv/bin/activate && alembic upgrade head`
- Start dev: `source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Alternativ startscript: `./scripts/start_app.sh`

## Runtime checks

- Lokal health: `curl -fsS http://127.0.0.1:8000/healthz`
- Extern/Tailscale som tidigare rapporterats: `http://100.109.34.20:8000` (verifiering i detta pass: se slutrapport)

## Verifieringskommandon

- `source venv/bin/activate && python -m pytest tests/ -v`
- `node --test tests/frontend/assistant-modules.test.mjs`
- `git diff --check`

## Senast verifierat utfall

- `source venv/bin/activate && python -m pytest tests/ -v` -> 70 passed.
- `node --test tests/frontend/assistant-modules.test.mjs` -> 9 passed.
- `git diff --check` -> pass.
- `curl -fsS http://127.0.0.1:8000/healthz` -> `{"status":"ok"}`.
- `curl -fsS http://100.109.34.20:8000/healthz` -> `{"status":"ok"}`.

## Säker smoke-procedur

1. Normal chattfråga via assistant respond -> 200, `write_intent=None`.
2. Komplett write-intent prompt -> 200, `write_intent` returneras, ingen canonical write sker i respond.
3. Ofullständig write-intent prompt -> 200, `questions` + `missing_fields`, apply blockerad.
4. Data-In (om testdata finns): `analyze` -> `promote` -> review -> apply.

## Vad man inte gör i smoke

- Inga destruktiva writes mot verklig data utan uttryckligt godkännande.
- Ingen auto-apply från frontend.
- Ingen bypass av `source_message_id`/replay-guard.

## Osäkerheter/kvarvarande risker

- Runtime smoke mot auth-skyddade endpoints kräver giltig login/token i miljöer där `BYPASS_AUTH=false`.
