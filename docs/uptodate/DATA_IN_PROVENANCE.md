# Data-In Provenance

## Titel
Data-In provenance-kontrakt (analyze -> promote -> apply)

**Senast verifierad:** 2026-04-28  
**Status:** Aktiv  
**Källa/grund:** `app/ai_services.py`, `app/main.py`, `app/models.py`, `app/schemas.py`

## Verifierad kedja

1. **Analyze** (`POST /households/{id}/ingest_ai/analyze`)
   - Returnerar `analysis_result_id`.
   - Lagrar serverägt analyze-resultat i `ingest_analysis_results`.
   - Lagrar `normalized_suggestions`, `document_summary`, provider/model/schema-version.
   - Beräknar `source_hash` från hushåll, källa, source_name, document_id och normaliserad input.

2. **Promote** (`POST /households/{id}/ingest_ai/promote`)
   - Kräver `analysis_result_id`.
   - Hämtar serverlagrat analyze-resultat.
   - Verifierar source channel/name/document-id och `source_hash`.
   - Vid mismatch blockeras promote med fel.
   - Skapar workflow-artefakter: `Document` + `ExtractionDraft`.
   - Skapar inte kanonisk ekonomisanning direkt.

3. **Apply**
   - Sker separat via dokument/draft apply-routes.
   - Först här sker canonical writes.

## Skydd som är implementerade

- Manipulerade klient-suggestions används inte som primär källa i promote.
- Stale eller mismatchat underlag stoppas via hash-kontroll.
- Saknat/okänt `analysis_result_id` stoppas.
- Promote utan validerade suggestions stoppas.

## Designkontrakt för GUI

- GUI ska lagra och skicka `analysis_result_id` oförändrat.
- GUI ska behandla analyze-svar som förslag, inte som redan skrivna poster.
- GUI får inte hoppa över review/apply-steg.

## Osäkerheter/kvarvarande risker

- Fullständig auditkedja över alla manuella beslut och alla mellanversioner är inte komplett dokumenterad i API-kontraktet.
- Full undo/rollback för alla workflow/apply-fall är inte verifierat i detta pass.
