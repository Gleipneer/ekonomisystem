# Framtida roadmap

Realistiska, arkitektoniskt rimliga förbättringar.
Inget av detta är implementerat — det är riktning, inte sanning.
Last updated: 2026-04-10.

## Prioritetsordning

### Fas A — Driftrobusthet och kvalitet (SNART)
- [ ] Dubblettkontroll mot kanonisk data (subscriptions, recurring costs)
- [ ] Evidenskedja: document → draft → applied entity (explicit provenance)
- [ ] Redigerbart ownership-fält i draft editing
- [ ] Playwright/browser-tester för kärn-flows
- [ ] `main.py` router-uppdelning (CRUD, workflow, AI, docs)

### Fas B — Smartare ingest (SNART)
- [ ] Regelmotor: godkänn mönster ("Google One = abonnemang")
- [ ] Återkommande-motor: upptäck mönster (månad, kvartal, år)
- [ ] Dubblettvarna vid samma underlag i annan kanal
- [ ] Utöka evidenskedjan med source notes
- [ ] Evaluate `ocrmypdf` för bättre skannade PDF:er

### Fas C — Analys och insikter (SENARE)
- [ ] Avvikelsemotor: ovanligt hög matkostnad, ny återkommande dragning
- [ ] Abonnemangsoptimering: dubbla/överlappande tjänster
- [ ] Kassaflödesförståelse: fasta vs rörliga, privat vs gemensamt
- [ ] Nästa-månad-prognos: sannolika utgifter
- [ ] Kompakta read models för AI (lägre tokens, mindre hallucination)
- [ ] Tidsmotor: förfallodagar, bindningstid, review-väntan

### Fas D — Fullt AI-lager (SENARE)
- [ ] Provider-abstraktion (byt OpenAI-modell utan kodändring)
- [ ] Käll-/auditspårning (original → OCR → AI → review → apply)
- [ ] Semantisk sök ("fråga om bilen, barnen, abonnemangen")
- [ ] Extern research: substitionsalternativ med källa och datum

### Fas E — Enterprise-funktioner (LONG TERM)
- [ ] Autentisering och per-användare access
- [ ] Bakgrundsjobb (påminnelser, periodisk processing)
- [ ] Metrics och observability
- [ ] Objektlagring (S3/MinIO) istället för lokal fillagring
- [ ] PostgreSQL som default-databas

## Vad som INTE bör byggas

- Full banksync / bankinloggning — out of scope
- Finance core / ledger — systemet är planerings-orienterat
- Bred AI-gateway med flera leverantörer — onödig komplexitet nu
- Autonom AI som skriver slutgiltig data — bryter kärnprincip
- Bred frontend redesign — nuvarande visuella språk fungerar
- Stora arkitekturomkastningar utan tydlig nytta
