# Source of Truth

Kanoniskt sanningsdokument för hushållsekonomiprojektet.
Last verified against code: 2026-04-27.

## Vad systemet är

Ett svenskt hushållsekonomisystem — en enda FastAPI-app med inbäddad
vanilla-JS-frontend — för planering, översikt och rådgivning kring
ett hushålls ekonomi.

Systemet lagrar strukturerad hushållsekonomidata (inkomster, lån,
abonnemang, försäkringar, fordon, tillgångar, kostnader), beräknar
deterministiska sammanfattningar, erbjuder scenariojämförelse,
dokumenthantering, rapportgenerering och import av strukturerade
bankpaket via den befintliga assistentchatten.

AI-funktioner (hushållsassistent och data-ingest) är separata ytor
som kräver extern OpenAI-nyckel. De skriver aldrig tyst till
kanonisk data.

## Vem det är till för

- Primärt: ett svenskt hushåll som vill ha praktisk koll på sin ekonomi
- Sekundärt: framtida AI-modeller/utvecklare som ska vidareutveckla systemet

## Scope — vad systemet gör idag

| Förmåga | Status |
|---|---|
| CRUD för 16 domänentiteter | ✅ Implementerat |
| Deterministisk hushållssammanfattning | ✅ Implementerat (inkluderar per-person-vy) |
| Boendekalkyl / housing evaluation | ✅ Implementerat |
| Scenariokörning med resultatjämförelse | ✅ Implementerat |
| Rapportögonblicksbilder (snapshots) | ✅ Implementerat |
| Dokumentuppladdning/nedladdning | ✅ Implementerat |
| Extraktionsutkast + explicit applicering | ✅ Implementerat |
| Optimeringsförslag (heuristisk scan) | ✅ Implementerat |
| Data-In AI (klassificering + extrahering) | ✅ Kräver OpenAI, serverägd analyze-provenance |
| Excel (.xlsx), OCR, PDF och text-chunking | ✅ Implementerat |
| `ECON_IMPORT_PACKAGE_V1` i assistentchatten | ✅ Implementerat |
| Legacy `.xls` staging via chat/dokument | ⚠️ Kan tas emot men kräver konvertering eller separat importpaket för strukturerad tolkning |
| Hushållsassistent med persisterad chatt | ✅ Kräver OpenAI för analys, lagrar trådar/messages i SQLite |
| Assistent-write via explicit apply | ✅ `source_message_id` krävs; saknade fält, osparade förslag och återspel blockerar commit |
| Advisory / extern deal-jämförelse | ⚠️ API-kontrakt finns, v1 returnerar stub utan externa anrop |
| Bank-PDF export (reportlab) | ✅ Implementerat |
| Merchant alias-normalisering | ✅ Implementerat |
| Risk-/readiness-signaler på sammanfattning | ✅ Implementerat |
| Autentisering (AppUser, AuthSession) | ✅ Implementerat |
| Bankkopplingar / transaktionsingest | ❌ Saknas |
| Bakgrundsjobb | ❌ Saknas |
| AI-gateway / provider-abstraktion | ❌ Saknas |
| Metrics / observability | ❌ Saknas |

## Kärnprinciper

1. **Sanning före allt.** Dokumentation speglar faktisk kod, aldrig tvärtom.
2. **AI skriver aldrig tyst.** All AI-output eller operatörspaket landar i workflow-artefakter först. Kanonisk data ändras bara via explicit apply eller tydligt bootstrapad hushållsnormalisering.
3. **Backend äger all finansmatematik.** Inga beräkningar i frontend.
4. **SQLite-first, filesystem-first.** Enkel drift utan externa beroenden.
5. **Svenska i UI.** Hushållsapp, inte enterprise-dashboard.
6. **Determinism framför magi.** Förutsägbar, reproducerbar logik.
7. **Explicit hellre än implicit.** Varje AI-interaktion kräver explicit prompt och explicit promote/apply.

## Systemgränser

```
┌──────────────────────────────────────────┐
│            Trusted Network               │
│         (Tailscale / localhost)          │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │         FastAPI (app.main:app)     │  │
│  │  ┌──────────┐  ┌───────────────┐  │  │
│  │  │ REST API │  │  Static SPA   │  │  │
│  │  │  (JSON)  │  │  (HTML/JS/CSS)│  │  │
│  │  └────┬─────┘  └───────────────┘  │  │
│  │       │                            │  │
│  │  ┌────┴─────┐  ┌───────────────┐  │  │
│  │  │ SQLAlch. │  │  ai_services  │──┼──┼──→ OpenAI API
│  │  │ + SQLite │  │   (httpx)     │  │  │    (extern)
│  │  └──────────┘  └───────────────┘  │  │
│  │       │                            │  │
│  │  ┌────┴─────┐                      │  │
│  │  │ Filesystem│ (uploaded_files/)   │  │
│  │  └──────────┘                      │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## Separation: nuläge vs målbild vs deferred

### Nuläge (implementerat och verifierat)
- Fullständig CRUD-backend för alla domänentiteter
- Deterministiska beräkningar (sammanfattning, boende, scenario, rapport)
- Real OpenAI-integration med Responses API
- Data-In med 9 klassificeringstyper, OCR, bank-paste
- Assistentchatten kan läsa `ECON_IMPORT_PACKAGE_V1` och skapa `Document` + `ExtractionDraft` + `UnresolvedQuestion`
- Samma assistentyta kan stage:a råfiler till dokumentflödet, inklusive val av `.xls` i UI
- Assistentchatten persisterar aktiv tråd + meddelanden i SQLite och laddar om samma konversation efter reload
- Assistenten har deterministisk modellrouting (`assistant_chat`, `assistant_write_intent`, `assistant_missing_info`, `deep_analysis`, `fallback_plain_text`) styrd av env + keywordregler
- Assistentens `write_intent` kan bara appliceras en gång när den matchar ett sparat assistantsvar (`source_message_id`), backend stoppar apply om intenten har `missing_fields` eller saknar obligatoriska ekonomifält
- Data-In `analyze` sparar serverägd `analysis_result_id` med källa/hash/version och normaliserade suggestions; `promote` kräver id:t, laddar serverns resultat och blockerar source/document-mismatch
- Aktiv sammanfattning och analys exkluderar `paused`/avslutade poster samt personbundna fakta för inaktiva personer
- Deterministisk analys returnerar även `advisory_analysis` som v1-stub: inga externa marknadsdata används eller blandas med fakta
- Svensk SPA-frontend med 16 routade sidor
- start_app.sh med venv, alembic, port-fallback, Tailscale-URL

### Planerad målbild (ej implementerat)
- Starkare dubblettkontroll mot kanonisk data
- Evidenskedja (document → draft → applied entity)
- Regelmotor för godkända mönster
- Återkommande-motor och påminnelser
- Read models för AI (kompakt, lägre tokenkostnad)
- Käll-/auditspårning

### Medvetet deferred
- Full banksync / bankinloggning
- Finance core / ledger
- Brett AI-gateway med flera providers
- Autonom AI-skrivning till kanonisk data
- Broad frontend redesign

## Assistentchattens persistens

- Chatthistorik lagras i `chat_threads` och `chat_messages`.
- Persistensen innehåller användarmeddelanden, assistantsvar och systembekräftelser.
- Strukturerat assistantsvar (`questions`, `write_intent`, provider/model/usage) lagras i `chat_messages.content_json` så UI kan återskapa samma kort efter reload.
- `POST /households/{id}/assistant/apply_intent` kräver `source_message_id` till ett sparat assistantsvar och jämför intent/data mot det lagrade förslaget före skrivning. Samma `source_message_id` kan inte appliceras igen.
- Apply-bekräftelser lagras som separata systemmeddelanden i samma tråd.
- Chatthistorik är en UX-/audityta och är inte samma sak som kanonisk ekonomisk sanning eller analysens sanningslager.

## Assistant UX status 2026-04-27

- Assistantkort renderas nu som tydliga ändringskort med status, sammanfattning och fältförändringar.
- Applybar intent visar CTA **Godkänn och spara**; intent med `missing_fields`/frågor visar blockerat informationsläge.
- Mobil (`<=768px`) kör single-column chat med kollapsat ekonomiläge via toggle-knapp, sticky composer och extra bottenpadding/safe-area för att undvika överlapp.
- Desktop behåller tvåkolumnslayout men använder samma action-cards och apply-logik.
- Kontextbudget i assistant-tråd är stramad: färre meddelanden och kortare historikinnehåll skickas till modellen för att minska tokenbelastning.
