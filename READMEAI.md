# READMEAI.md — Sanering/Handoff

Last updated: 2026-04-04.

## Saneringsstatus

- `main` pullad och synkad.
- `cursor/development-environment-setup-a192` rebasad mot senaste `main`.
- Konflikt löst sanningsenligt i `READMEAI.md`.
- Branch innehöll migrationslucka för `MerchantAlias`; ny Alembic-revision skapad:
  - `alembic/versions/20260404_000002_add_merchant_aliases.py`
- Kontraktsdrift fixad mellan AI-guidning och domänmodell:
  - `variability_class_values` använder nu `semi_fixed` (inte `semi_variable`).
- Verifierad branch mergad till `main`.

## Verifiering i denna körning

- `alembic upgrade head` körd och grön.
- `python -m pytest tests/ -v` körd och grön (`24 passed`).
- App startad lokalt via `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Endpoints verifierade:
  - `/` (UI laddar)
  - `/docs` (Swagger laddar)
  - `/healthz` (`{"status":"ok"}`)
- Intelligence layer verifierad i runtime med deterministisk mock av AI-anrop:
  - merchant alias normalisering: `NFX` → `Netflix`
  - duplicate indicator sattes
  - ownership candidate sattes (`private`)
  - why_suggested sattes
  - risk signals returnerade i summary (`high_fixed_ratio`, `pending_reviews`)

## Miljönoteringar från verifiering

- Python-paket installerade från `requirements.txt` i venv (bl.a. `reportlab`, `Pillow`, `pytesseract`).
- Systempaket installerade för OCR-runtime:
  - `tesseract-ocr`
  - `tesseract-ocr-swe`

## Kritiska sanningar

- Inga nya stora features byggdes i denna pass; fokus var sanering/synk/verifiering.
- Ingest är fortsatt advisory: ingen tyst canonical write.
- Risk signals är deterministiska (ingen AI-magi).
- Enum/kontrakt mellan `models`, `schemas`, `ai_services` är synkade efter fix.
- Ny modell (`MerchantAlias`) har nu motsvarande Alembic-migration.

## Git-status efter sanering

- `main` innehåller verifierad merge från `cursor/development-environment-setup-a192`.
- Branch och `main` ska hållas i spegel efter push i denna pass.
