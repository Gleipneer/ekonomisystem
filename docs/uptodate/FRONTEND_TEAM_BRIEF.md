# Frontend Team Brief

## Titel
Frontend-brief för alternativa GUI ovanpå samma backend

**Senast verifierad:** 2026-04-28  
**Status:** Aktivt kontrakt för GUI-team  
**Källa/grund:** `app/main.py`, `app/schemas.py`, `app/ai_services.py`, `app/static/app.js`

## Vad backend äger

- Datavalidering, canonical writes, apply-gates och replay-skydd.
- All finansmatematik och sammanställning (`/analysis`, `/summary`, rapport/scenario-körning).
- AI-säkerhetskontrakt: suggestion != sanning.
- Document ingest provenance (serverägd analyze-output + hash-kontroller).

## Vad frontend får/inte får göra

- Får: visualisera fakta, osäkerhet, frågor och förslag.
- Får: guida användaren genom review/apply.
- Får inte: skriva kanonisk data direkt från LLM-svar.
- Får inte: visa apply när backend markerar ofullständighet (`missing_fields`, frågor, mismatch, replay).
- Får inte: räkna interna överföringar som konsumtionsutgift utan explicit regel.
- Får inte: dölja osäker data/provenance.

## Backend-owned invariants

- Canonical writes sker endast via backend apply-routes.
- Frontend kan rendera suggestions men får inte behandla dem som sanning.
- Apply aktiveras endast i backend-säkrat tillstånd.
- `source_message_id` krävs för assistant apply.
- Replay-protection blockerar återanvänd apply på samma källmeddelande.
- `missing_fields`/`questions` blockerar apply.
- `paused`/`inactive` data får inte räknas som aktiva kostnader/skulder.
- Interna överföringar ska vara visuellt separata från utgifter.

## Nödvändiga GUI-vyer

- Dashboard/overview
- Household/persons
- Incomes
- Recurring costs
- Subscriptions
- Loans/debts
- Insurances
- Documents/ingest workbench
- Assistant/chat
- Review/apply queue
- Reports/scenarios
- Settings/auth/session

## UX-principer

- Visa osäkerhet explicit (confidence, uncertainty_notes, validation_status).
- Visa `missing_fields` och `questions` som blockerande krav.
- Visa apply-knapp endast när backendsignal tillåter.
- Separera transfer/saving från kostnad.
- Separera aktiv/inaktiv/paused/closed i listor och summeringar.
- Visa provenance/source där det finns (`source_message_id`, `analysis_result_id`, dokument-id).
- Inga dolda writes.

## Assistant state machine (förslag)

### `idle`
- **Visas:** tom eller senaste tråd, input aktiv.
- **Tillåtet:** skriva prompt, ladda om tråd.
- **Förbjudet:** apply utan nytt backend-svar.

### `sending`
- **Visas:** spinner/lås på skicka.
- **Tillåtet:** avbryt UI-operation lokalt.
- **Förbjudet:** dubbelskick av samma prompt.

### `answer_received`
- **Visas:** svarstext utan write-intent.
- **Tillåtet:** följdfråga.
- **Förbjudet:** apply-knapp.

### `questions_required`
- **Visas:** frågor + saknade fält.
- **Tillåtet:** fyll i kompletteringar.
- **Förbjudet:** apply.

### `write_intent_draft`
- **Visas:** föreslagen ändring med osäkerhet/provenance.
- **Tillåtet:** redigera via nytt promptflöde eller avstå.
- **Förbjudet:** auto-apply.

### `apply_ready`
- **Visas:** tydlig CTA "Godkänn och spara".
- **Tillåtet:** explicit apply med `source_message_id`.
- **Förbjudet:** implicit apply vid navigation/reload.

### `applying`
- **Visas:** låst CTA med väntestatus.
- **Tillåtet:** vänta på backendresultat.
- **Förbjudet:** parallell apply.

### `applied`
- **Visas:** systembekräftelse och resultat.
- **Tillåtet:** fortsätta chat/review.
- **Förbjudet:** re-apply av samma källa.

### `blocked`
- **Visas:** backend-block (mismatch/replay/missing fields).
- **Tillåtet:** hämta ny tråd/svar och börja om.
- **Förbjudet:** klient-bypass.

### `error`
- **Visas:** felmeddelande (503/502/400/409/404).
- **Tillåtet:** retry enligt användarval.
- **Förbjudet:** tyst fallback som skapar write-intent.

## Document ingest state machine (förslag)

- `uploaded`: fil/text mottagen.
- `analyzed`: analyze-svar med `analysis_result_id` och suggestions.
- `promote_ready`: användaren väljer promote.
- `promoted_to_draft`: Document + ExtractionDraft skapade.
- `review_required`: utkast granskas/ev. kopplas.
- `apply_ready`: validerad apply möjlig.
- `applied`: kanoniska mutationer genomförda.
- `rejected/error`: avvisat eller fel; kräver nytt underlag.

## GUI-testscenarier

- Lägg till Netflix 149 kr/mån och verifiera att apply kräver explicit klick.
- Lägg till ofullständig försäkring och verifiera blockerat apply + frågor.
- Fråga normal ekonomifråga och verifiera inget write-intent/apply.
- Kör dokumentingest med testfil om tillgänglig och verifiera analyze -> promote -> review -> apply.
- Verifiera att intern överföring inte visas som konsumtionsutgift.
- Verifiera att inaktiv/betald skuld inte räknas som aktiv.
- Verifiera att apply blockeras vid stale/mismatched `source_message_id`.

## Tre GUI-koncept

### A. Chat-first ekonomicenter
- **Huvudflöde:** chat -> intent-kort -> apply.
- **Styrkor:** snabbt för vardagsärenden.
- **Risker:** användare kan feltolka förslag som fakta.
- **Måste respektera:** source_message_id, missing_fields-block, no-auto-write.

### B. Dashboard-first hushållsöversikt
- **Huvudflöde:** overview -> drill-down -> åtgärd.
- **Styrkor:** hög läsbarhet av nuläge/trender.
- **Risker:** osäker data kan döljas i aggregering om UI är slarvigt.
- **Måste respektera:** aktiv/inaktiv-separation, transfer-vs-expense-separation, backend-beräknad sanning.

### C. Workbench-first datagranskning
- **Huvudflöde:** dokument/drafts -> review -> apply queue.
- **Styrkor:** bäst kontroll och provenance.
- **Risker:** högre komplexitet och fler steg.
- **Måste respektera:** analyze_result_id + source-hash chain, explicit apply, inga direkta canonical writes från suggestion.

## Osäkerheter/kvarvarande risker

- Auth-routes är implementerade i backend:
  - `POST /auth/register`
  - `POST /auth/token`
- GUI bör hantera onboardingflöde där ny användare kan sakna `household_id` och därför blockeras från household-routes tills koppling är satt.
