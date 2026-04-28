# Historisk rapport. För aktuell status, se docs/uptodate/.
#
# Ekonomisystem Review 2026-04-27

## Syfte och läsanvisning

Detta dokument är en sammanhållen systembedömning av `ekonomisystem` efter
korrekthetsgenomgången den 27 april 2026. Det ersätter inte
`docs/SOURCE_OF_TRUTH.md`, `docs/AI_CONTRACT.md` eller
`docs/HANDOFF_FOR_OTHER_MODELS.md`; de är fortfarande de kanoniska
arbetsdokumenten. Den här rapporten är en värdering: vad som fungerar, vad som
är svagt, vad som bör byggas härnäst och hur systemet bör rankas.

Bedömningen utgår från faktisk kod, dokumentation och verifiering:

- `source venv/bin/activate && python -m pytest tests/ -v` -> 77 passed.
- `node --test tests/frontend/assistant-modules.test.mjs` -> 4 passed.
- `merge analyze .`, `merge eval .` och `merge work .` körda.
- Kända begränsningar från `SOURCE_OF_TRUTH`, `AI_CONTRACT` och senaste
  korrekthetsgenomgång är medräknade.

## Sammanfattande betyg

**Totalpoäng: 79 / 100**

Systemet är en fungerande och relativt robust v1 för ett självhostat svenskt
hushållsekonomisystem. Den viktigaste styrkan är att ekonomisk sanning numera
ligger i deterministisk backendlogik och att AI-ytorna är tydligt avgränsade.
Efter senaste hårdningen är assistant-write betydligt säkrare: sparad källa
krävs, apply är one-shot, öppna frågor blockerar UI-apply och backend stoppar
ofullständiga create-intents även om LLM missar `missing_fields`.

Systemet är däremot inte redo att beskrivas som ett komplett privatekonomiskt
operativsystem. Det saknar bankkopplingar, faktisk extern deal-jämförelse,
bakgrundsjobb, metrics och en mer underhållbar modulstruktur. Betyget hamnar
därför högt för v1-funktion och
säkerhetskontrakt, men lägre för skalbarhet, driftobservability och framtida
förvaltningsbarhet.

## Rangordnad delbedömning

| Område | Poäng | Motivering |
|---|---:|---|
| Testad v1-korrekthet | 88 | Full backendsvit och frontendmodultest passerar. Kritiska AI-write- och aktiv-data-fall har regressionsskydd. |
| AI-write governance | 86 | `respond` skriver inte kanoniskt, `apply_intent` kräver sparat assistantsvar, matchande data och one-shot source. Backend stoppar saknade fält. |
| Deterministisk analysmotor | 83 | Historical/cycle/planned/subscription/forecast finns och testas. Aktiv filtrering och payday edge cases är förbättrade. |
| Domänmodell och SQLite-v1 | 80 | Datamodellen täcker många hushållsentiteter och fungerar lokalt. Evidenskedja och dubblettlogik är fortfarande delvis implicit. |
| Dokument- och ingestflöde | 82 | PDF/OCR/text/Excel, drafts och explicit apply finns. `analyze -> promote` använder nu serverägd `analysis_result_id` med source-hash/provenance och klientmanipulation av suggestions ignoreras. |
| Produktnytta för hushåll | 77 | Systemet kan redan ge översikt, rapporter, planerade köp, kostnadssignaler och chat-styrd datainmatning. Saknar banksync och automatiska flöden. |
| Frontend/UX | 74 | Svenska SPA:n har bred täckning och assistantflödet är nu ärligare. `app.js` är stor, legacy-blandad och vissa flöden är svåra att underhålla. |
| Drift och självhosting | 74 | Startscript, SQLite, Alembic, Tailscale-väg och Ubuntu-docs finns. Metrics, strukturerad loggning och servicehärdning saknas. |
| Arkitektur och maintainability | 62 | Fungerar men centrala filer är mycket stora: `main.py`, `ai_services.py`, `app.js`. `merge` markerar dem fortsatt som hotspots. |
| Extern rådgivning/marknadsdata | 35 | API-kontrakt finns men v1 är stubbat. Ingen verklig deal-lookup eller marknadsjämförelse används. |

## Nuvarande status

### Implementerat och verifierat

- FastAPI-monolith med inbäddad vanilla-JS frontend.
- SQLite-first med lokal filhantering.
- Sessionbaserad autentisering via `AppUser` och `AuthSession`.
- CRUD och sammanfattningar för hushåll, personer, inkomster, lån,
  återkommande kostnader, abonnemang, försäkringar, fordon, tillgångar,
  dokument, scenarios och rapporter.
- Deterministisk hushållssammanfattning med per-person-vy.
- Deterministisk analysyta:
  - historical analysis
  - cycle/payday engine
  - planned purchases engine
  - subscription signals
  - forecast/actions
  - advisory stub utan extern data
- Data-In AI:
  - analyze skriver inte kanoniskt
  - promote skapar Document + ExtractionDraft
  - apply är separat och explicit
  - PDF/text/OCR/Excel-vägar finns
- Assistantchat:
  - persisterad tråd och meddelanden
  - explicit modellrouting (`assistant_chat`, `assistant_write_intent`, `assistant_missing_info`, `deep_analysis`, `fallback_plain_text`)
  - `write_intent` sparas i chatthistorik
  - `apply_intent` kräver `source_message_id`
  - replay av samma source blockeras
  - öppna frågor/missing fields blockerar UI-apply
  - backend stoppar ofullständiga create-intents
- Dokument-workbench visar reviewdata och döljer enkla draft-apply-knappar när
  ett dokument har föreslagen objektkedja.

### Implementerat men partiellt

- Legacy `.xls` kan hanteras bättre än tidigare, men bör fortfarande betraktas
  som känsligare än `.xlsx`.
- Advisory/external deal layer är kontrakterat men stubbat.
- Ingest-promote skriver inte kanonisk data och har nu serverägd beviskedja via
  `analysis_result_id`; kvarvarande gap är främst full audit/undo över hela systemet.
- Evidens från dokument till draft till applicerad entitet finns i praktiken,
  men är inte ett fullständigt provenance-system.
- Dubblettkontroll finns i delar av workflowet men är inte heltäckande mot all
  kanonisk data.

### Saknas eller är tydligt deferred

- Bankkopplingar och automatisk transaktionsingest.
- Bakgrundsjobb för återkommande analyser, påminnelser och automatiska scans.
- Metrics, strukturerad loggning, dashboards och operativ observability.
- Verklig extern marknadsdata för abonnemang/deal comparison.
- Provider-abstraktion för flera AI-leverantörer.
- Finance core/ledger med bokföringslika principer.
- Full audit/provenance och undo för alla write-operationer.

## Vad som är bra

### 1. Rätt sanningsgräns

Systemets viktigaste kvalitet är att AI inte är sanningskälla. AI analyserar,
föreslår och skapar workflow-artefakter, men kanonisk data kräver explicit
apply. Det är rätt arkitektur för ett ekonomisystem.

### 2. Deterministisk kärna

Beräkningar ligger i backend och är testbara. Analysmotorn är separerad från
presentation och AI. Det gör att samma input kan ge samma output utan prompt-
eller modellvariation.

### 3. Praktisk v1-yta

Systemet är inte bara en prototypvy. Det har dokumentflöde, rapporter,
scenarios, assistant, auth, OCR/text-ingest och faktiska DB-modeller. Det finns
nog funktion för att använda systemet i ett hushåll med manuell datainmatning.

### 4. Säker assistant-write efter hårdning

Senaste genomgången tog bort flera farliga luckor:

- tomt sparat intent-data kan inte längre godkänna godtycklig request-data
- samma source kan inte appliceras flera gånger
- systemmeddelanden kan inte användas som apply-källa
- saknade ekonomifält får inte tyst bli defaultvärden som `0 kr`, `monthly`
  eller `Abonnemang`
- frontend visar inte apply när förslaget fortfarande kräver svar

### 5. Verifieringsdisciplin

Det finns en faktisk testsvit och den kördes efter ändringarna. Det är en stor
skillnad mot ett system som bara ser färdigt ut i UI.

## Vad som är mindre bra

### 1. Stora centrala filer

`app/main.py`, `app/ai_services.py` och `app/static/app.js` är stora hotspots.
Det ökar risken vid varje ändring och gör systemet långsammare att förstå för
nya modeller eller utvecklare.

Bedömning: detta är den största tekniska skulden.

### 2. Promote-provenance är delvis stängd

`/ingest_ai/promote` skapar bara workflow-artefakter, och kräver nu ett
serverägt `analysis_result_id`. Promote hämtar serverlagrade suggestions,
validerar source/document-hash och blockerar mismatch. Kvarstående förbättring
är bredare audit/undo över alla write-flöden.

### 3. Ingen verklig bankdata-loop

Systemet kan hantera manuella paket, dokument och texter, men saknar automatisk
bankkoppling. Därför är det ännu inte ett kontinuerligt ekonomisystem; det är
ett manuellt eller semi-manuellt beslutsstöd.

### 4. Advisory är inte verklig ännu

Extern deal comparison är korrekt avgränsad som stub, men användarvärdet är
begränsat tills systemet kan jämföra abonnemang mot riktiga marknadsalternativ.

### 5. Observability och drift är tunna

För självhosting räcker `start_app.sh`, `/healthz` och docs långt. För stabil
produktion saknas metrics, strukturerade logs, backup-/restore-test och bättre
runtimeövervakning.

### 6. UI:t bär mycket ansvar

Frontend har många flöden i samma kodbas och vissa äldre/importerade delar.
Senaste hårdningen gjorde UI ärligare, men långsiktigt bör backend äga ännu mer
av workflow-state och frontend bli tunnare.

## Rekommenderade framtida expansioner

### Prioritet 1: Bygg vidare på stängd ingest-provenance

1. Lägg retention-policy och enkel auditvy för `ingest_analysis_results`.
2. Lägg explicit provenancekedja:
   `Document -> ExtractionDraft -> AppliedEntityLink -> CanonicalEntity`.
3. Gör apply-operationer reversibla där det är rimligt.
4. Lägg dubblettkontroll mot kanonisk data, inte bara drafts.

Effekt: högre förtroende och lägre risk för dubbla eller felaktiga ekonomifakta.

### Prioritet 2: Bryt upp hotspots

1. Dela `main.py` i routers:
   `households`, `documents`, `assistant`, `ingest`, `analysis`, `crud`.
2. Dela `ai_services.py` i:
   provider client, assistant service, ingest service, promotion service.
3. Dela `app.js` i routade vyer eller fortsätt modulbrytning under
   `app/static/js/`.

Effekt: snabbare utveckling, lägre regressionsrisk och lättare arbete för AI-
agenter.

### Prioritet 3: Gör systemet kontinuerligt

1. Bankimport eller åtminstone återkommande kontoutdragspipeline.
2. Schemalagda analyser efter ny data.
3. Automatiska men icke-kanoniska förslag:
   subscriptions, riskzoner, kommande betalningar, sparutrymme.
4. Read models för AI med hård tokenbudget.

Effekt: systemet går från manuell dashboard till aktiv ekonomimotor.

### Prioritet 4: Verklig advisory

1. Lägg read-only external deal adapters.
2. Spara externa jämförelser som advisory-artefakter, inte fakta.
3. Visa `external_data_used`, källa, tidpunkt och osäkerhet i varje råd.
4. Börja med abonnemang/försäkring där datamodellen redan finns.

Effekt: tydligt användarvärde utan att externa uppgifter blandas med intern
sanning.

### Prioritet 5: Drift och kvalitet

1. Backup-/restore-runbook och test.
2. Strukturerad logging för apply, ingest och assistant.
3. Metrics för fel, latency, AI-tokenkostnad och OCR/ingest-status.
4. Smoke-test mot startad app i CI eller release-gate.

Effekt: systemet blir enklare att lita på över tid.

## Riskregister

| Risk | Nivå | Kommentar | Rekommenderad åtgärd |
|---|---:|---|---|
| Stora hotspots | Hög | `main.py`, `ai_services.py`, `app.js` är svåra att ändra säkert. | Router-/serviceuppdelning stegvis. |
| Promote utan serverägd analyze-provenance | Låg | Serverägd `analysis_result_id` + source/document-hash blockar osäker promote och klientmanipulation av suggestions. | Lägg retention-policy och full auditlogg för provenance-tabellen. |
| Manuell dataförsörjning | Medel | Systemet blir snabbt inaktuellt utan bank/importloop. | Bankimport eller standardiserad importpipeline. |
| Advisory stub | Medel | Användarvärdet i externa besparingar är begränsat. | Read-only externa adapters. |
| Svag observability | Medel | Fel kan vara svåra att följa i drift. | Loggar, metrics, auditvy. |
| Legacy frontendyta | Medel | Risk för döda eller dubbla flöden. | Fortsatt ärlig disabling och modulär frontend. |

## Slutomdöme

Systemet bör betraktas som en **stark v1 / tidig v2-kandidat**, inte som ett
färdigt bankklassat privatekonomisystem. Det viktigaste är på plats:
deterministiska beräkningar, explicit write-gateway, workflow-first dokument-
ingest och tydlig separation mellan fakta, planer, analys och rådgivning.

Det som håller tillbaka betyget är inte en enskild bugg utan mognadsnivå:
stora filer, ingen bankloop, stubbat advisorylager och
begränsad driftobservability. Om nästa utvecklingspass fokuserar på provenance,
hotspot-uppdelning och kontinuerlig dataförsörjning kan systemet realistiskt
höjas från **79/100** till cirka **86-90/100** för ett självhostat hushållsbruk.

## Patchnote 2026-04-27 (kväll) - Assistant apply UX + mobilchat

- Assistantens write/apply-flöde är nu praktiskt användbart i UI: tydliga ändringskort, tillståndsetiketter och CTA **Godkänn och spara** när förslaget är applybart.
- Svar med `missing_fields`/frågor visar blockerat läge ("Behöver mer information") utan apply-knapp.
- Bekräftelseprompter som "skriv in nu" bypassar inte säkerhetsgränsen; backend svarar med explicit hänvisning till godkännandeknappen.
- Mobilvy är omgjord till single-column chat med kollapsbart ekonomiläge, förbättrad scrollyta och composer-safe-area-padding.
- Kontextmängden till assistanten är reducerad via kortare och mer kompakt historik i backend, för lägre tokenkostnad.

## Verifieringsnotering 2026-04-27 (kvalitetskedja)

- `analysis_result_id` är persistat i serverägd DB-lagring via tabellen
  `ingest_analysis_results` (modell `IngestAnalysisResult`, migration
  `20260427_122800_add_ingest_analysis_results.py`).
- `/ingest_ai/promote` läser serverlagrat analyze-resultat via
  `analysis_result_id` och använder `normalized_suggestions` samt
  `source_hash` från databasen; klientens `suggestions` används inte som
  sanningskälla.
- Säkerhetskontraktet för Data-In provenance är därmed stängt för v1-nivån,
  med kvarvarande förbättringar främst kring retention/audit/undo.
