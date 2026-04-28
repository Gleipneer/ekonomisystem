# ER-diagram

Datamodellen som den faktiskt finns implementerad i `app/models.py`.
Last verified against code: 2026-04-10.

## Mermaid ER-diagram

```mermaid
erDiagram
    Household ||--o{ Person : "has members"
    Household ||--o{ Loan : "has loans"
    Household ||--o{ RecurringCost : "has costs"
    Household ||--o{ SubscriptionContract : "has subscriptions"
    Household ||--o{ InsurancePolicy : "has policies"
    Household ||--o{ Vehicle : "has vehicles"
    Household ||--o{ Asset : "has assets"
    Household ||--o{ HousingScenario : "has scenarios"
    Household ||--o{ Document : "has documents"
    Household ||--o{ ExtractionDraft : "has drafts"
    Household ||--o{ OptimizationOpportunity : "has opportunities"
    Household ||--o{ Scenario : "has what-if scenarios"
    Household ||--o{ ScenarioResult : "has results"
    Household ||--o{ ReportSnapshot : "has snapshots"
    Household ||--o{ MerchantAlias : "has aliases"

    Person ||--o{ IncomeSource : "earns income"
    Person }o--o{ Loan : "may own (optional)"
    Person }o--o{ RecurringCost : "may own (optional)"
    Person }o--o{ SubscriptionContract : "may own (optional)"
    Person }o--o{ Asset : "may own (optional)"
    Person }o--o{ Vehicle : "may own (optional)"

    Document ||--o{ ExtractionDraft : "has drafts"
    Scenario ||--o{ ScenarioResult : "produces results"

    Loan }o--o| Asset : "linked_asset (optional)"
    Vehicle }o--o| Loan : "linked loan (optional)"
    Vehicle }o--o| InsurancePolicy : "linked policy (optional)"
    InsurancePolicy }o--o| Asset : "linked_asset (optional)"

    Household {
        int id PK
        string name
        string currency
        string primary_country
        datetime created_at
    }

    Person {
        int id PK
        int household_id FK
        string name
        string role
        string income_share_mode
        bool active
    }

    IncomeSource {
        int id PK
        int person_id FK
        string type
        float gross_amount
        float net_amount
        enum frequency
        string regularity
        string source
    }

    Loan {
        int id PK
        int household_id FK
        int person_id FK
        string type
        string lender
        float current_balance
        float nominal_rate
        enum repayment_model
        float required_monthly_payment
        string status
    }

    RecurringCost {
        int id PK
        int household_id FK
        int person_id FK
        string category
        float amount
        enum frequency
        bool mandatory
        enum variability_class
        enum controllability
    }

    SubscriptionContract {
        int id PK
        int household_id FK
        int person_id FK
        enum category
        string provider
        string product_name
        float current_monthly_cost
        date binding_end_date
        bool auto_renew
    }

    InsurancePolicy {
        int id PK
        int household_id FK
        string type
        string provider
        float premium_monthly
        float deductible
        date renewal_date
    }

    Vehicle {
        int id PK
        int household_id FK
        int owner_person_id FK
        string make
        string model
        int year
        float estimated_value
    }

    Asset {
        int id PK
        int household_id FK
        int person_id FK
        string type
        string institution
        float market_value
        float liquid_value
        bool pledged
    }

    HousingScenario {
        int id PK
        int household_id FK
        string label
        float purchase_price
        float down_payment
        float mortgage_needed
        float rate_assumption
    }

    Document {
        int id PK
        int household_id FK
        string document_type
        string file_name
        string mime_type
        string checksum
        text extracted_text
        string extraction_status
        string storage_path
    }

    ExtractionDraft {
        int id PK
        int household_id FK
        int document_id FK
        string target_entity_type
        json proposed_json
        json review_json
        float confidence
        string status
        string model_name
    }

    OptimizationOpportunity {
        int id PK
        int household_id FK
        string kind
        string target_entity_type
        int target_entity_id
        string title
        float estimated_monthly_saving
        string status
    }

    Scenario {
        int id PK
        int household_id FK
        string label
        json change_set_json
    }

    ScenarioResult {
        int id PK
        int household_id FK
        int scenario_id FK
        json result_json
        float monthly_delta
        float yearly_delta
    }

    MerchantAlias {
        int id PK
        int household_id FK
        string alias
        string canonical_name
        string category_hint
    }

    ReportSnapshot {
        int id PK
        int household_id FK
        string type
        date as_of_date
        json result_json
    }
```

## Modell-lager

### Kärnlager (Household Core)
- `Household` — toppnivåcontainer
- `Person` — hushållsmedlem, äger inkomstkällor

### Ekonomiska poster (Income, Liability, Cost, Asset)
- `IncomeSource` — inkomst kopplad till person
- `Loan` — skuld/lån med amorteringsmodell
- `RecurringCost` — återkommande kostnad (mat, transport, etc.)
- `SubscriptionContract` — avtal (mobil, bredband, streaming)
- `InsurancePolicy` — försäkring
- `Vehicle` — fordon med driftskostnader
- `Asset` — tillgång (konto, sparande, fastighet)

### Planering och utvärdering
- `HousingScenario` — boendekalkyl
- `Scenario` — vad-om-analys med JSON-ändringar
- `ScenarioResult` — resultat av scenariokörning
- `ReportSnapshot` — fryst sammanfattning vid tidpunkt

### Dokument och AI-arbetsflöde
- `Document` — dokumentmetadata + lagringssökväg
- `ExtractionDraft` — AI-förslag, inväntar granskning/applicering
- `OptimizationOpportunity` — heuristisk förbättringsmöjlighet
- `MerchantAlias` — per-hushåll alias → kanoniskt handelsnamn

## Index och nycklar

- Alla modeller har `id` som primärnyckel (autoincrement integer)
- Foreign keys med `ondelete=CASCADE` för household → barnentiteter
- Foreign keys med `ondelete=SET NULL` för valfria relationer (person, asset, vehicle)
- Inget explicit unikt constraint på MerchantAlias (alias per household)

## Enums i modellen

| Enum | Värden |
|---|---|
| `IncomeFrequency` | monthly, yearly, weekly, biweekly, daily |
| `LoanRepaymentModel` | annuity, fixed_amortization, interest_only, manual |
| `VariabilityClass` | fixed, semi_fixed, variable |
| `Controllability` | locked, negotiable, reducible, discretionary |
| `SubscriptionCategory` | mobile, broadband, electricity, streaming, gym, alarm, software, insurance, membership, other |
