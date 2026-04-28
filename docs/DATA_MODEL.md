# Datamodell

Entiteter, relationer, invariants och normaliseringsflöden.
Last verified against code: 2026-04-10.

Se även `docs/ER_DIAGRAM.md` för visuellt ER-diagram.

## Entitetsöversikt

### Kärnentiteter (Household Core)

| Entitet | Tabell | Beskrivning |
|---|---|---|
| Household | `households` | Toppnivå-container. Alla ekonomiska poster tillhör ett hushåll. |
| Person | `persons` | Hushållsmedlem. Inkomster kopplas till personer. |

### Ekonomiska poster

| Entitet | Tabell | Relation | Beskrivning |
|---|---|---|---|
| IncomeSource | `income_sources` | Person → Income | Inkomst (lön, CSN, pension, etc) |
| Loan | `loans` | Household → Loan | Skuld med amorteringsmodell |
| RecurringCost | `recurring_costs` | Household → Cost | Återkommande kostnad (mat, transport) |
| SubscriptionContract | `subscription_contracts` | Household → Sub | Avtal (mobil, bredband, streaming) |
| InsurancePolicy | `insurance_policies` | Household → Policy | Försäkring |
| Vehicle | `vehicles` | Household → Vehicle | Fordon med driftskostnader |
| Asset | `assets` | Household → Asset | Tillgång (konto, sparande, fastighet) |

### Planering

| Entitet | Tabell | Beskrivning |
|---|---|---|
| HousingScenario | `housing_scenarios` | Boendekalkyl med köpesumma, handpenning, ränta |
| Scenario | `scenarios` | Vad-om-analys med JSON-ändringar |
| ScenarioResult | `scenario_results` | Resultat: månadsdelta, årsdelta, likviditetsdelta |
| ReportSnapshot | `report_snapshots` | Fryst sammanfattning vid tidpunkt |

### Workflow och AI

| Entitet | Tabell | Beskrivning |
|---|---|---|
| Document | `documents` | Dokumentmetadata + filsökväg |
| ExtractionDraft | `extraction_drafts` | AI-förslag, inväntar granskning |
| OptimizationOpportunity | `optimization_opportunities` | Heuristisk förbättringsmöjlighet |
| MerchantAlias | `merchant_aliases` | Per-hushåll alias → kanoniskt namn |

## Invariants

1. **Household är rot.** Alla ekonomiska poster refererar `household_id`.
2. **CASCADE vid raderade hushåll.** Alla barnentiteter raderas.
3. **SET NULL vid radering av valfria relationer** (person, asset, vehicle).
4. **ExtractionDraft ≠ kanonisk data.** Draft.proposed_json är förslag, inte sanning.
5. **MerchantAlias är per hushåll.** Inget globalt alias-register.
6. **Enums är strikta.** `frequency`, `variability_class`, `controllability` har fasta värden.
7. **ReportSnapshot är immutabel.** Fryst JSON som aldrig uppdateras.

## Alembic-migrationer

| Revision | Beskrivning |
|---|---|
| `20260402_000001_baseline` | Alla initiala tabeller |
| `20260404_000002_add_merchant_aliases` | MerchantAlias-tabell |
| `20260404_000003_document_review_workflow` | Workflow-fält på Document + ExtractionDraft |
| `20260404_000004_add_draft_apply_summary` | apply_summary_json på ExtractionDraft |

## Normaliseringsflöden

### Hur rådata blir användbar hushållsekonomidata

```
1. Råtext (klistrad, PDF, OCR, bank-paste)
   ↓
2. Textormalisering (NBSP, zero-width, form feeds)
   ↓
3. Hint-detektering (faktura-, abonnemangs-, banknykelord)
   ↓
4. AI-klassificering (9 typer) + fältextraktion
   ↓
5. Schema-validering (Pydantic create-scheman)
   ↓
6. Suggestions returneras till klient (INGEN DB-skrivning)
   ↓
7. Explicit promote → Document + ExtractionDraft (workflow)
   ↓
8. Explicit apply → Kanonisk entitet skapas
```

### Merchant alias-normalisering

```
1. Alla aliases laddas för hushållet
2. Ingest-text normaliseras (lowercase, strip)
3. Alias-matchning: "nfx" → "Netflix"
4. Normaliserad text skickas till AI
5. AI-förslag använder kanoniskt namn
```

## Frekvens-normalisering (beräkningslogik)

Alla belopp normaliseras till månads- och årsbelopp i `calculations.py`:

| Frekvens | → Månadsbelopp | → Årsbelopp |
|---|---|---|
| daily | × 30 | × 365 |
| weekly | × 4.33 | × 52 |
| biweekly | × 2.17 | × 26 |
| monthly | × 1 | × 12 |
| yearly | ÷ 12 | × 1 |
