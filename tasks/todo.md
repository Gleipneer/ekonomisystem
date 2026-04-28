# Historisk arbetslogg. För aktuell status och kontrakt, se docs/uptodate/.
#
# Fullständig korrekthetsgenomgång 2026-04-27

## Plan - Assistant model routing 2026-04-27
- [x] Kartlägg nuvarande model/config-användning i assistant + ingest + docs/tests.
- [x] Implementera explicit route-policy med deterministiska regler och env-styrda modeller.
- [x] Behåll no-auto-write och one-shot apply; fallback ska alltid vara text + `write_intent=null`.
- [x] Lägg regressionstester för route-val, fallbackmodell och configstyrning.
- [x] Uppdatera docs (`AI_CONTRACT`, `SOURCE_OF_TRUTH`, `.env.example`) och verifiera med testsvit + health + diff-check.

## Review - Assistant model routing 2026-04-27
- Implementerat: explicit assistant-routing med routes `assistant_chat`, `assistant_write_intent`, `assistant_missing_info`, `deep_analysis` och `fallback_plain_text`.
- Säkerhet: ingen route kan skriva kanonisk data i `respond`; fallback returnerar alltid text utan `write_intent`.
- Konfigurering: nya env-nycklar `ECON_AI_*` styr modellval utan hårdkodning i flödeskod.

## Plan - Data-In provenance hardening 2026-04-27
- [x] Inför serverägd persistence för `analyze` med `analysis_result_id`, source hash, normalized suggestions och schema-version.
- [x] Kräv `analysis_result_id` i `promote`, ladda serverlagrat analyze-resultat och ignorera klientägda suggestions.
- [x] Validera source/document match vid promote och blockera osäkra äldre flöden med tydliga fel.
- [x] Lägg regressionstester för saknat id, manipulerad klientpayload, giltig promote och source-hash mismatch.
- [x] Uppdatera docs (`SOURCE_OF_TRUTH`, review-rapport) och verifiera med full testsvit + frontendtest + `git diff --check`.

## Plan - Kvalitetskedja closeout 2026-04-27
- [x] Kör repo-hygien (`git status --short`, `git diff --check`) och åtgärda endast trailing whitespace i utpekade filer.
- [x] Kör om verifiering (`pytest` + frontend node-test) och bekräfta gröna gates.
- [x] Sanningsgranska `analysis_result_id`-persistens i kod/migration/modell.
- [x] Uppdatera review/todo med explicit status för serverägd persistence och promote-provenance.

## Review - Data-In provenance hardening 2026-04-27
- Implementerat: serverägd analyze-provenance med ny tabell `ingest_analysis_results`, API-kontrakt för `analysis_result_id` och promote-validering mot source/document hash.
- Säkerhet: promote kan inte längre skapa drafts från manipulerade klient-suggestions; endast serverlagrad analyze-output används.
- Verifiering: riktade regressionstester + full backendsvit + frontend assistant-modultest passerar.

## Plan
- [x] Etablera baslinje med `git status`, `merge analyze .`, `merge work .`, backendtester och frontendtester.
- [x] Låt agentsvärm granska tre kritiska ytor: deterministisk analys, AI/write-kontrakt och frontendflöden.
- [x] Fixa endast bekräftade kontraktsfel med minimal kodändring.
- [x] Verifiera med riktade tester, full backendtestsvit, frontendtest och `merge`-utvärdering.
- [x] Dokumentera implementerat, partiellt och kvarvarande luckor.

## Review
Klar 2026-04-27.

Implementerat i kod:
- Assistentens `apply_intent` är nu one-shot per `source_message_id` och kräver att källan är ett sparat assistantsvar.
- Apply jämför sparad/requestad intent-data även när sparad data är tom och stoppar ofullständiga create-intents även om LLM missat `missing_fields`.
- Aktiv ekonomisanning exkluderar `paused`/avslutade poster och personbundna fakta för inaktiva personer.
- Payday-cykeln använder faktisk sista dag per månad för löndag 29-31 och analysrouten kan få explicit `as_of`.
- Assistent-UI visar inte apply när förslaget har öppna frågor, saknade fält eller saknar sparat meddelande-ID.
- Dokument-workbench döljer enkla draft-apply-knappar när dokumentet har föreslagen objektkedja.
- Dokumenttextläsning returnerar stabil tuple-shape för document-id ingest/promote.

Verifiering:
- `source venv/bin/activate && python -m pytest tests/ -v` -> 77 passed.
- `node --test tests/frontend/assistant-modules.test.mjs` -> 4 passed.
- `merge analyze .`, `merge eval .`, `merge work . ... --validation ... --guard ...` körda. Installerad `merge` saknar `verify`; `merge work` fortsätter BLOCK:a på hotspot-policy/no-nearby-tests trots angivna valideringar.

Kvarvarande/partiellt:
- `/ingest_ai/promote` är fortfarande en workflow-route (Document/ExtractionDraft) men kräver nu serverägd analyze-provenance och ignorerar klientmanipulerade suggestions.
- `main.py`, `ai_services.py` och `app.js` är fortsatt stora hotspots enligt `merge`.

---

# Systemrapport 2026-04-27

## Plan
- [x] Skapa ett komplett granskningsdokument som sammanfattar nuläge, styrkor, svagheter, framtida expansioner och poängsättning.
- [x] Hänvisa till verifierade källor och senaste genomgången utan att ersätta kanoniska sanningsdokument.

## Plan - Assistant apply workflow + mobil UX 2026-04-27
- [x] Diagnostisera write/apply-kedjan (persistens, source_message_id, apply-endpoint, replay/missing-fields-guard).
- [x] Implementera tydliga action-cards för write_intent med apply/blockerat tillstånd.
- [x] Förbättra mobilchatten till single-column med kollapsbart ekonomiläge och säkrare composer-scroll.
- [x] Behåll safety-contract: inget auto-write i `assistant/respond`, explicit apply med `source_message_id`.
- [ ] Verifiera med backendtester, frontendmodultester, runtime-health och diff-check.

## Review - Assistant apply workflow + mobil UX 2026-04-27
- Backend: svar på bekräftelsefraser ("skriv in nu") leder till apply-hänvisning, inte canonical write.
- Backend: assistant-historik till modellen är kompakterad (färre roller, kortare innehåll) för lägre tokenkostnad.
- Frontend: write_intent visas som tydligt ändringskort med status + CTA "Godkänn och spara" när apply är tillåtet.
- Frontend: missing_fields/frågor blockerar apply-CTA, batchförslag utan backend-kontrakt markeras som blockerade.
- Frontend: mobilvy använder single-column, togglad ekonomiöversikt och förbättrad bottenpadding/safe-area i chatten.
