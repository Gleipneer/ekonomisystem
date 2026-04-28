# API Contract for Frontend

## Titel
Frontendrelevant API-kontrakt baserat på faktiska routes

**Senast verifierad:** 2026-04-28  
**Status:** Aktiv  
**Källa/grund:** Route-deklarationer i `app/main.py`, payloadmodeller i `app/schemas.py`

## Auth/session-ram

- Middleware skyddar API-routes; bypass kan aktiveras med `BYPASS_AUTH=true` (dev/test).
- Publica ytor: `/`, `/healthz`, docs/openapi, statiska assets, `/auth/*`.
- Auth-endpoints:
  - `POST /auth/register` - registrera användare.
  - `POST /auth/token` - login och token/session.
- Nyregistrerad användare med `household_id=None` blockeras från household-routes tills household-koppling finns.

## Bas/endpoints

### `GET /healthz`
- **Syfte:** Liveness.
- **Auth:** publik.
- **Request:** ingen.
- **Response:** `{"status":"ok"}`.
- **Typ:** read-only.

### `GET /`
- **Syfte:** servera GUI.
- **Auth:** publik.
- **Typ:** read-only.

## Household och domän-CRUD

Faktiska grupper i `app/main.py`: `households`, `persons`, `income_sources`, `loans`, `recurring_costs`, `subscription_contracts`, `insurance_policies`, `vehicles`, `financial_assets`, `housing_scenarios`, `documents`, `extraction_drafts`, `optimization_opportunities`, `scenarios`, `scenario_results`, `report_snapshots`, `merchant_aliases`, `planned_purchases`.

Gemensamt kontrakt:
- **Metoder:** `GET/POST/PUT/DELETE` per resurs (plus vissa specialrutter).
- **Auth:** kräver household-access via backend.
- **Request/response:** Pydanticmodeller i `app/schemas.py` (t.ex. `HouseholdCreate/Read`, `RecurringCostCreate/Read`, `SubscriptionContractCreate/Read`).
- **Typ:** canonical-write för create/update/delete.
- **UI-regel:** aldrig auto-anropa write-endpoints utan explicit användarval.

## Assistant-kontrakt

### `GET /households/{household_id}/assistant/thread`
- **Syfte:** hämta aktiv chattråd.
- **Auth:** hushållskontroll.
- **Response:** `ChatThreadRead` med meddelanden.
- **Typ:** read-only.

### `POST /households/{household_id}/assistant/thread/reset`
- **Syfte:** inaktivera aktiv tråd.
- **Typ:** workflow-write.
- **UI-regel:** endast explicit reset.

### `POST /households/{household_id}/assistant/respond`
- **Syfte:** AI-svar + frågor + ev. `write_intent` för review.
- **Request:** `AssistantPromptRequest` (`prompt`, ev. `conversation`).
- **Response:** `AssistantPromptResponse` (`answer`, `questions`, `write_intent`, provider/model/usage).
- **Typ:** workflow-write (sparar chatthistorik), ej canonical-write.
- **UI-regel:** får anropas av användarens prompt; får inte tolkas som auto-apply.

### `POST /households/{household_id}/assistant/apply_intent`
- **Syfte:** canonical apply av tidigare assistant-förslag.
- **Request:** `AssistantIntentApplyRequest`, kritiskt fält `source_message_id`.
- **Response:** status/resultat per intenttyp.
- **Typ:** canonical-write.
- **Får aldrig auto-anropas:** ja, kräver explicit användargodkännande.

### `POST /households/{household_id}/assistant/import_files`
- **Syfte:** stage:a uppladdade filer till dokumentflöde.
- **Request:** multipart `files[]`, ev. `prompt`.
- **Response:** `AssistantPromptResponse` från system (inte LLM-apply).
- **Typ:** workflow-write.

## Document + Data-In kontrakt

### `POST /households/{household_id}/ingest_ai/analyze`
- **Syfte:** AI-analys av text/dokument till klassificering och suggestions.
- **Request:** `IngestAnalyzeRequest` (`input_text` eller `document_id`, `source_channel`, m.m.).
- **Response:** `IngestAnalyzeResponse` inkl. `analysis_result_id`.
- **Typ:** workflow-write (sparar serverägt analyze-resultat), ej canonical-write.
- **Får aldrig auto-anropas i bakgrunden:** bör vara explicit användarhandling p.g.a kostnad och tolkningsrisk.

### `POST /households/{household_id}/ingest_ai/promote`
- **Syfte:** promote serverlagrat analyze-resultat till `Document` + `ExtractionDraft`.
- **Request:** `IngestPromoteRequest` med `analysis_result_id`.
- **Response:** `IngestPromoteResponse`.
- **Typ:** workflow-write, ej canonical-write.
- **Får aldrig auto-anropas:** ja, explicit reviewsteg.

### `GET /documents`, `POST /documents`, `POST /documents/upload`, `GET /documents/{id}`, `PUT /documents/{id}`, `DELETE /documents/{id}`
- **Syfte:** dokumenthantering.
- **Typ:** mixed read/canonical-write på dokumentmetadata.

### `GET /documents/{id}/review`
- **Syfte:** samlad workflowstatus för dokument/drafts.
- **Typ:** read-only.

### `POST /documents/{id}/apply`
- **Syfte:** applicera dokumentworkflow till kanoniska mutationer.
- **Request/response:** `DocumentApplyRequest` -> `DocumentApplyResponse`.
- **Typ:** canonical-write.
- **Får aldrig auto-anropas:** ja.

### `POST /extraction_drafts/{id}/apply`
- **Syfte:** applicera ett draft till kanonisk entitet.
- **Typ:** canonical-write.
- **Får aldrig auto-anropas:** ja.

## Analys/rapporter/scenario

### `GET /households/{household_id}/summary`
- **Syfte:** deterministisk hushållssammanfattning.
- **Typ:** read-only.

### `GET /households/{household_id}/analysis`
- **Syfte:** full deterministisk analys (ingen LLM).
- **Typ:** read-only.

### `GET /households/{household_id}/analysis/cycle`
- **Syfte:** payday cycle-status.
- **Typ:** read-only.

### `POST /households/{household_id}/report_snapshots/generate`
- **Syfte:** skapa rapportsnapshot.
- **Typ:** canonical-write (ny snapshotrad), user-triggered.

### Scenario-endpoints (`/scenarios`, `/scenario_results`, `/scenarios/{id}/run`)
- **Syfte:** scenariehantering och körning.
- **Typ:** mixed read/canonical-write.

## Schemareferenser

- Assistant: `AssistantPromptRequest`, `AssistantPromptResponse`, `AssistantIntentApplyRequest` i `app/schemas.py`.
- Data-In: `IngestAnalyzeRequest/Response`, `IngestPromoteRequest/Response` i `app/schemas.py`.
- Dokumentworkflow: `DocumentWorkflowRead`, `DocumentApplyRequest`, `DocumentApplyResponse`.

## Osäkerheter/kvarvarande risker

- Onboardingflödet för att tilldela `household_id` efter registrering är fortfarande en produktfråga för GUI/backoffice.
