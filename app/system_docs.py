SYSTEM_DESCRIPTION = """# Household Economics System Validation

## Scope

This is an auxiliary text artifact, not the canonical handoff source.

Use the uppercase docs under `docs/` for the current source of truth.

The current runtime is a private household-finance platform served from one FastAPI app.
It includes:

- web UI on `/`
- OpenAPI docs on `/docs`
- health check on `/healthz`
- full CRUD for all domain entities
- deterministic household summary calculations
- housing scenario evaluation
- scenario execution against adjustment JSON
- report snapshot generation
- document upload and download
- extraction draft application into canonical tables
- optimisation scan suggestions
- a deterministic household assistant endpoint

## Entity Coverage

- Household
- Person
- IncomeSource
- Loan
- RecurringCost
- SubscriptionContract
- InsurancePolicy
- Vehicle
- Asset
- HousingScenario
- Document
- ExtractionDraft
- OptimizationOpportunity
- Scenario
- ScenarioResult
- ReportSnapshot

## Functional Checklist

### Core App

- `GET /` serves the frontend
- `GET /healthz` returns status
- `GET /docs` serves Swagger UI

### CRUD

Each entity supports:

- list
- create
- retrieve
- update with partial payload
- delete

### Calculations

- `GET /households/{id}/summary`
- `GET /housing_scenarios/{id}/evaluate`
- `POST /scenarios/{id}/run`
- `POST /households/{id}/report_snapshots/generate`

### Documents

- `POST /documents/upload`
- `GET /documents/{id}/download`

### Workflow Helpers

- `POST /households/{id}/optimization_scan`
- `POST /extraction_drafts/{id}/apply`
- `POST /households/{id}/assistant/respond`

## Manual Validation Flow

1. Open `/`.
2. Create a household.
3. Verify records are visible in UI and via `/docs`.
4. Upload a document and download it again.
5. Create a scenario and run it.
6. Create a housing scenario and evaluate it.
7. Generate a report snapshot from a household.
8. Create an extraction draft and apply it.
9. Run optimisation scan and inspect generated opportunities.

## Test Validation

Automated tests cover:

- root and health check
- household CRUD and partial update
- document upload and download
- household summary and report generation
- scenario run and housing evaluation
- optimisation scan
- calculation helpers
"""
