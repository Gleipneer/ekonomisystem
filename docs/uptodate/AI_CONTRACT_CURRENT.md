# AI Contract Current

## Titel
Aktuellt AI-kontrakt (assistant + Data-In)

**Senast verifierad:** 2026-04-28  
**Status:** Aktiv  
**Källa/grund:** `app/ai_services.py`, `app/main.py`, `app/schemas.py`, tester i `tests/test_assistant_schema_contract.py` och `tests/test_chat_persistence.py`

## Implementerat nu

### Assistant `respond`

- Route: `POST /households/{household_id}/assistant/respond`.
- Kör structured output för write-relevanta prompts, textläge för vanlig chat/deep analysis enligt route-policy.
- Sparar chatthistorik, men gör ingen canonical write.

### Strict schema-fix (OpenAI Responses)

- `AnalysisStructuredOutput.write_intent` använder `AssistantWriteIntentStructured`.
- `AssistantWriteIntentStructured` har `data_json: str` i stället för fri `dict[str, Any]`.
- `_normalize_structured_write_intent()` mappar `data_json -> dict` server-side.
- Ogiltig JSON i `data_json` degraderas säkert till `{}` och ambiguity-notis; ingen auto-write triggas.
- `_force_openai_strict()` hanterar object utan properties för att undvika ogiltig strict-schema-nod.

### Fallback-regel

- Först structured anrop.
- Vid schema/provider-fel av typen strict-schemafel används plain-text fallback.
- Fallback returnerar: `answer`, `questions=[]`, `write_intent=None`.
- Fallback får aldrig skapa apply/write-intent.

### Apply-kontrakt

- `POST /households/{household_id}/assistant/apply_intent` kräver `source_message_id`.
- Backend laddar sparat assistant-meddelande och verifierar att write-intent finns.
- `missing_fields` blockerar apply.
- One-shot/replay-skydd: samma `source_message_id` kan inte appliceras två gånger.
- Systembekräftelse loggas med `source_message_id`, intent och resultat.

## Data-In och provenance koppling

- `analyze` skapar serverägt `analysis_result_id`.
- `promote` kräver `analysis_result_id` och kontrollerar source-hash/source-kanal/source-name/document-id.
- Klientmanipulerade suggestions används inte som källa för promote.

## Implementerat vs planerat

- **Implementerat:** route-policy med `assistant_chat`, `assistant_write_intent`, `assistant_missing_info`, `deep_analysis`, `fallback_plain_text`.
- **Implementerat:** strict schema-hantering med structured write-intent + servermappning.
- **Implementerat:** no-auto-write i respond och explicit apply-gateway.
- **Planerat/ej verifierat i detta pass:** separat "modellrouting-blueprint" utanför nuvarande regler; inga bevis i synlig kod för en mer avancerad router än nuvarande keyword/rule-baserade urval.

## Säkerhetskrav som inte får försvagas

- No-auto-write i `assistant/respond`.
- Apply kräver explicit steg och giltigt `source_message_id`.
- Replay-skydd (one-shot) på source message.
- Data-In provenance-kedja (`analysis_result_id` + source-hash-match).
- Fallback får inte producera write-intent.

## Osäkerheter/kvarvarande risker

- Semantiskt tveksamma men syntaktiskt giltiga write-intents kan fortfarande uppstå och måste hanteras via UI-review + backendvalidering.
