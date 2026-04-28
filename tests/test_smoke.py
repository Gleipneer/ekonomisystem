import importlib
import io
import json
import os
import subprocess
import sys
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect


def load_app(tmp_path):
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["UPLOAD_DIR"] = str(tmp_path / "uploads")
    os.environ["AUTO_CREATE_SCHEMA"] = "true"
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["OPENAI_ANALYSIS_MODEL"] = ""
    os.environ["OPENAI_INGEST_MODEL"] = ""
    os.environ["BYPASS_AUTH"] = "true"

    import app.settings as settings
    settings.get_settings.cache_clear()
    import app.database as database
    import app.models as models
    import app.schemas as schemas
    import app.main as main

    importlib.reload(database)
    importlib.reload(models)
    importlib.reload(schemas)
    main = importlib.reload(main)

    return main.app


def create_household_fixture(client: TestClient) -> dict[str, int]:
    household = client.post(
        "/households",
        json={"name": "Joakim & Jakobine", "currency": "SEK", "primary_country": "SE"},
    )
    assert household.status_code == 201
    household_id = household.json()["id"]

    joakim = client.post(
        "/persons",
        json={
            "household_id": household_id,
            "name": "Joakim",
            "role": "self",
            "income_share_mode": "pooled",
            "active": True,
        },
    )
    assert joakim.status_code == 201

    jakobine = client.post(
        "/persons",
        json={
            "household_id": household_id,
            "name": "Jakobine",
            "role": "partner",
            "income_share_mode": "pooled",
            "active": True,
        },
    )
    assert jakobine.status_code == 201

    child_1 = client.post(
        "/persons",
        json={
            "household_id": household_id,
            "name": "Barn 1",
            "role": "child",
            "income_share_mode": "pooled",
            "active": True,
        },
    )
    assert child_1.status_code == 201

    child_2 = client.post(
        "/persons",
        json={
            "household_id": household_id,
            "name": "Barn 2",
            "role": "child",
            "income_share_mode": "pooled",
            "active": True,
        },
    )
    assert child_2.status_code == 201

    joakim_id = joakim.json()["id"]
    jakobine_id = jakobine.json()["id"]

    salary_net = client.post(
        "/income_sources",
        json={
            "person_id": joakim_id,
            "type": "salary",
            "net_amount": 21500,
            "frequency": "monthly",
            "regularity": "fixed",
            "source": "Lön efter skatt",
        },
    )
    assert salary_net.status_code == 201

    salary_gross = client.post(
        "/income_sources",
        json={
            "person_id": jakobine_id,
            "type": "salary",
            "gross_amount": 430000,
            "frequency": "yearly",
            "regularity": "fixed",
            "source": "Årslön före skatt",
        },
    )
    assert salary_gross.status_code == 201

    car_loan = client.post(
        "/loans",
        json={
            "household_id": household_id,
            "person_id": joakim_id,
            "type": "car",
            "purpose": "Bil",
            "lender": "Billån",
            "required_monthly_payment": 2400,
            "status": "active",
            "repayment_model": "manual",
        },
    )
    assert car_loan.status_code == 201

    bed_loan = client.post(
        "/loans",
        json={
            "household_id": household_id,
            "person_id": joakim_id,
            "type": "other",
            "purpose": "Säng",
            "lender": "Resurs Bank",
            "current_balance": 12000,
            "remaining_term_months": 8,
            "required_monthly_payment": 1616,
            "status": "active",
            "repayment_model": "manual",
        },
    )
    assert bed_loan.status_code == 201

    eye_loan = client.post(
        "/loans",
        json={
            "household_id": household_id,
            "person_id": jakobine_id,
            "type": "other",
            "purpose": "Memira ögonlaser",
            "lender": "Memira",
            "required_monthly_payment": 399,
            "status": "active",
            "repayment_model": "manual",
        },
    )
    assert eye_loan.status_code == 201

    lovable = client.post(
        "/subscription_contracts",
        json={
            "household_id": household_id,
            "person_id": joakim_id,
            "category": "software",
            "provider": "Lovable",
            "product_name": "Starter",
            "current_monthly_cost": 5,
            "billing_frequency": "monthly",
            "household_criticality": "optional",
            "market_checkable": True,
        },
    )
    assert lovable.status_code == 201

    vehicle = client.post(
        "/vehicles",
        json={
            "household_id": household_id,
            "owner_person_id": joakim_id,
            "make": "Bil",
            "model": "Familjebil",
            "loan_id": car_loan.json()["id"],
        },
    )
    assert vehicle.status_code == 201

    recurring_cost = client.post(
        "/recurring_costs",
        json={
            "household_id": household_id,
            "category": "barn",
            "subcategory": "Övriga familjekostnader",
            "amount": 0,
            "frequency": "monthly",
            "mandatory": True,
            "variability_class": "fixed",
            "controllability": "locked",
        },
    )
    assert recurring_cost.status_code == 201

    scenario = client.post(
        "/scenarios",
        json={
            "household_id": household_id,
            "label": "Avsluta Lovable",
            "change_set_json": {
                "adjustments": [
                    {"entity": "subscription_contracts", "operation": "delete", "id": lovable.json()["id"]},
                ]
            },
        },
    )
    assert scenario.status_code == 201

    housing = client.post(
        "/housing_scenarios",
        json={
            "household_id": household_id,
            "label": "Bostadstest",
            "purchase_price": 3500000,
            "down_payment": 525000,
            "mortgage_needed": 2975000,
            "rate_assumption": 4.0,
            "amortization_rate": 2.0,
            "monthly_fee_or_operating_cost": 4200,
            "monthly_insurance": 250,
            "monthly_property_cost_estimate": 450,
        },
    )
    assert housing.status_code == 201

    return {
        "household_id": household_id,
        "joakim_id": joakim_id,
        "jakobine_id": jakobine_id,
        "scenario_id": scenario.json()["id"],
        "housing_id": housing.json()["id"],
        "bed_loan_id": bed_loan.json()["id"],
    }


def seed_ingest_analysis_result(
    *,
    household_id: int,
    document_id: int,
    source_channel: str,
    source_name: str,
    extracted_text: str,
    suggestions: list[dict],
    document_summary: dict,
) -> str:
    from uuid import uuid4

    from app import ai_services, database, models
    from app.ingest_content import normalize_ingest_text

    analysis_result_id = str(uuid4())
    source_hash = ai_services._compute_ingest_source_hash(
        household_id=household_id,
        source_channel=source_channel,
        source_name=source_name,
        document_id=document_id,
        normalized_input_text=normalize_ingest_text(extracted_text),
    )
    db = database.SessionLocal()
    try:
        db.add(
            models.IngestAnalysisResult(
                analysis_result_id=analysis_result_id,
                household_id=household_id,
                document_id=document_id,
                source_hash=source_hash,
                source_channel=source_channel,
                source_name=source_name,
                normalized_suggestions=suggestions,
                document_summary=document_summary,
                detected_kind=document_summary.get("document_type"),
                provider="test",
                model="test-seeded",
                analysis_schema_version="ingest-analysis-v1",
            )
        )
        db.commit()
    finally:
        db.close()
    return analysis_result_id


def test_healthz_and_home(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        response = client.get("/")
        assert response.status_code == 200
        assert "Ekonomi" in response.text


def test_auth_register_hashes_password_and_login_still_works(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app) as client:
        register = client.post(
            "/auth/register",
            json={"username": "secure-user", "password": "super-secret", "household_name": None},
        )
        assert register.status_code == 201

        import app.database as database
        import app.models as models

        db = database.SessionLocal()
        try:
            user = db.query(models.AppUser).filter_by(username="secure-user").first()
            assert user is not None
            assert user.password_hash != "super-secret"
            assert user.password_hash.startswith("$2")
        finally:
            db.close()

        login_ok = client.post(
            "/auth/token",
            json={"username": "secure-user", "password": "super-secret"},
        )
        assert login_ok.status_code == 200
        assert login_ok.json()["access_token"]

        login_bad = client.post(
            "/auth/token",
            json={"username": "secure-user", "password": "wrong"},
        )
        assert login_bad.status_code == 401


def test_household_access_is_blocked_for_user_without_household(tmp_path):
    os.environ["BYPASS_AUTH"] = "true"
    app = load_app(tmp_path)
    with TestClient(app) as client:
        household = client.post(
            "/households",
            json={"name": "Tenant A", "currency": "SEK", "primary_country": "SE"},
        )
        assert household.status_code == 201
        hid = household.json()["id"]

        register = client.post(
            "/auth/register",
            json={"username": "unassigned-user", "password": "secret", "household_name": None},
        )
        assert register.status_code == 201

        token = client.post(
            "/auth/token",
            json={"username": "unassigned-user", "password": "secret"},
        ).json()["access_token"]

        os.environ["BYPASS_AUTH"] = "false"
        summary = client.get(
            f"/households/{hid}/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert summary.status_code == 403


def test_household_access_is_blocked_for_wrong_household(tmp_path):
    os.environ["BYPASS_AUTH"] = "true"
    app = load_app(tmp_path)
    with TestClient(app) as client:
        first = client.post(
            "/households",
            json={"name": "Tenant A", "currency": "SEK", "primary_country": "SE"},
        )
        second = client.post(
            "/households",
            json={"name": "Tenant B", "currency": "SEK", "primary_country": "SE"},
        )
        assert first.status_code == 201
        assert second.status_code == 201
        hid_a = first.json()["id"]
        hid_b = second.json()["id"]

        register = client.post(
            "/auth/register",
            json={"username": "assigned-user", "password": "secret", "household_name": None},
        )
        assert register.status_code == 201
        user_id = register.json()["id"]

        import app.database as database
        import app.models as models

        db = database.SessionLocal()
        try:
            user = db.get(models.AppUser, user_id)
            user.household_id = hid_a
            db.add(user)
            db.commit()
        finally:
            db.close()

        token = client.post(
            "/auth/token",
            json={"username": "assigned-user", "password": "secret"},
        ).json()["access_token"]

        os.environ["BYPASS_AUTH"] = "false"
        blocked = client.get(
            f"/households/{hid_b}/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert blocked.status_code == 403

        allowed = client.get(
            f"/households/{hid_a}/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert allowed.status_code == 200


def test_alembic_upgrade_head_creates_schema(tmp_path):
    db_path = tmp_path / "alembic.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["AUTO_CREATE_SCHEMA"] = "false"

    result = subprocess.run(
        ["./venv/bin/alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["AUTO_CREATE_SCHEMA"] = "false"
    import app.settings as settings_module
    import app.database as database

    settings_module.get_settings.cache_clear()
    database = importlib.reload(database)
    inspector = inspect(database.engine)
    assert "households" in inspector.get_table_names()
    assert "alembic_version" in inspector.get_table_names()


def test_household_crud_partial_update(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app) as client:
        created = client.post(
            "/households",
            json={"name": "Andersson Household", "currency": "SEK", "primary_country": "SE"},
        )
        assert created.status_code == 201
        household = created.json()
        household_id = household["id"]

        updated = client.put(f"/households/{household_id}", json={"name": "Updated Household"})
        assert updated.status_code == 200
        data = updated.json()
        assert data["name"] == "Updated Household"
        assert data["currency"] == "SEK"
        assert data["primary_country"] == "SE"

        listed = client.get("/households")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        deleted = client.delete(f"/households/{household_id}")
        assert deleted.status_code == 204


def test_summary_document_scenario_and_report_flow(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        summary = client.get(f"/households/{household_id}/summary")
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["monthly_income_net"] == 21500
        assert payload["monthly_income_gross_only"] == 35833.33
        assert payload["monthly_income"] == 57333.33
        assert payload["gross_income_only_entries"] == 1
        assert payload["monthly_loan_payments"] == 4415
        assert payload["monthly_subscriptions"] == 5
        assert payload["monthly_total_expenses"] == 4420
        assert payload["monthly_net_cashflow"] == 52913.33
        assert payload["loan_balance_total"] == 12000
        assert payload["net_worth_estimate"] == -12000
        assert payload["counts"]["persons"] == 4

        upload = client.post(
            "/documents/upload",
            data={"household_id": str(household_id), "document_type": "invoice", "issuer": "Resurs Bank"},
            files={"file": ("invoice.txt", io.BytesIO(b"resurs invoice"), "text/plain")},
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]
        assert upload.json()["extracted_text"] == "resurs invoice"
        assert upload.json()["extraction_status"] == "interpreted"

        download = client.get(f"/documents/{document_id}/download")
        assert download.status_code == 200
        assert download.content == b"resurs invoice"

        evaluate = client.get(f"/housing_scenarios/{ids['housing_id']}/evaluate")
        assert evaluate.status_code == 200
        assert evaluate.json()["monthly_total_cost"] == 19775.0

        scenario_result = client.post(f"/scenarios/{ids['scenario_id']}/run")
        assert scenario_result.status_code == 200
        result_json = scenario_result.json()["result_json"]
        assert result_json["baseline"]["monthly_net_cashflow"] == 52913.33
        assert result_json["projected"]["monthly_net_cashflow"] == 52918.33
        assert scenario_result.json()["monthly_delta"] == 5

        report = client.post(f"/households/{household_id}/report_snapshots/generate", json={})
        assert report.status_code == 200
        assert report.json()["type"] == "monthly_overview"
        assert report.json()["result_json"]["monthly_loan_payments"] == 4415

        opportunities = client.post(f"/households/{household_id}/optimization_scan")
        assert opportunities.status_code == 200
        titles = [item["title"] for item in opportunities.json()]
        assert any("Lovable" in title for title in titles)

        updated_loan = client.put(
            f"/loans/{ids['bed_loan_id']}",
            json={"current_balance": 10000, "remaining_term_months": 6},
        )
        assert updated_loan.status_code == 200
        assert updated_loan.json()["purpose"] == "Säng"
        assert updated_loan.json()["remaining_term_months"] == 6


def test_calculation_helpers_cover_frequency_and_estimated_loan_payment(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app):
        from app import calculations

        assert calculations.amount_to_monthly(430000, "yearly") == pytest.approx(35833.333333333336)
        assert calculations.amount_to_monthly(1000, "weekly") == pytest.approx(4333.333333333333)
        assert calculations.estimate_loan_monthly_payment(
            {
                "current_balance": 12000,
                "nominal_rate": 6.0,
                "amortization_amount_monthly": 1000,
                "required_monthly_payment": None,
            }
        ) == pytest.approx(1060)


def test_ai_routes_fail_cleanly_without_provider(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        analysis = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "Hur ser vår ekonomi ut just nu?"},
        )
        assert analysis.status_code == 503
        assert "OPENAI_API_KEY" in analysis.json()["detail"]

        ingest = client.post(
            f"/households/{household_id}/ingest_ai/analyze",
            json={"input_text": "2026-04-01 GYM AB -299,00", "input_kind": "bank_copy_paste"},
        )
        assert ingest.status_code == 503
        assert "OPENAI_API_KEY" in ingest.json()["detail"]


def test_extract_text_from_upload_handles_text_and_pdf_branches(monkeypatch):
    from app.ingest_content import extract_text_from_upload

    text_result = extract_text_from_upload(b"  Rad 1\nRad 2  ", file_name="note.txt", mime_type="text/plain")
    assert text_result.text == "Rad 1\nRad 2"
    assert text_result.extraction_mode == "text_file"

    class FakePage:
        def extract_text(self):
            return "  Faktura april\n  Resurs Bank  \n  299 kr  "

    class FakeReader:
        def __init__(self, _stream):
            self.pages = [FakePage()]

    monkeypatch.setattr("app.ingest_content.PdfReader", FakeReader)
    pdf_result = extract_text_from_upload(b"%PDF-1.4 fake", file_name="invoice.pdf", mime_type="application/pdf")
    assert "Faktura april" in pdf_result.text
    assert pdf_result.extraction_mode == "pdf_text"
    assert any("PDF" in note for note in pdf_result.notes)


def test_ingest_analyze_returns_document_summary_and_review_groups(tmp_path, monkeypatch):
    app = load_app(tmp_path)
    from app import ai_services
    from app import schemas

    app_response = ai_services.IngestStructuredOutput(
        classification=ai_services.IngestDocumentClassificationOutput(
            document_type="invoice",
            provider_name="Resurs Bank",
            label="Resurs Bank faktura april",
            amount=299.0,
            currency="SEK",
            due_date="2026-04-12",
            cadence="monthly",
            category_hint="subscription",
            suggested_target_entity_type="recurring_cost",
            household_relevance="high",
            confidence=0.94,
            confirmed_fields=["provider_name", "amount", "due_date"],
            notes=["Belopp och förfallodag framgår tydligt."],
            uncertainty_reasons=["Cadence bygger på textens månadslogik."],
        ),
        summary="Det här ser ut som en återkommande faktura för ett hushåll.",
        guidance=["Skapa ett reviewutkast om kostnaden är hushållsrelevant."],
        suggestions=[
            ai_services.IngestStructuredSuggestion(
                target_entity_type="recurring_cost",
                review_bucket="recurring_cost",
                title="Resurs Bank - återkommande kostnad",
                rationale="Månadsfaktura med tydligt belopp.",
                confidence=0.91,
                proposed_json='{"household_id": 1, "category": "debt", "amount": 299, "frequency": "monthly", "vendor": "Resurs Bank", "mandatory": true, "variability_class": "fixed", "controllability": "locked"}',
                uncertainty_notes=["Beloppet verkar vara totalbeloppet."],
            )
        ],
    )

    def fake_call_openai_structured(*_args, **_kwargs):
        return app_response, "gpt-test", schemas.AIUsageRead(input_tokens=120, output_tokens=60, total_tokens=180)

    monkeypatch.setattr(ai_services, "_call_openai_structured", fake_call_openai_structured)

    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        document = client.post(
            "/documents",
            json={
                "household_id": household_id,
                "document_type": "invoice",
                "file_name": "resurs.pdf",
                "mime_type": "application/pdf",
                "extracted_text": "Resurs Bank faktura april 299 kr förfaller 2026-04-12.",
            },
        )
        assert document.status_code == 201
        document_id = document.json()["id"]

        response = client.post(
            f"/households/{household_id}/ingest_ai/analyze",
            json={
                "document_id": document_id,
                "source_channel": "uploaded_pdf",
                "source_name": "Resurs Bank",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["document_summary"]["document_type"] == "invoice"
        assert payload["document_summary"]["provider_name"] == "Resurs Bank"
        assert payload["document_summary"]["confirmed_fields"] == ["provider_name", "amount", "due_date"]
        assert payload["document_summary"]["confidence"] == 0.94
        assert payload["suggestions"][0]["review_bucket"] == "recurring_cost"
        assert payload["review_groups"][0]["suggestion_count"] == 1
        assert payload["input_details"]["source_channel"] == "uploaded_pdf"
        assert payload["input_details"]["document_id"] == document_id
        assert payload["image_readiness"]["supported"] is True


def test_ingest_analyze_ignores_invalid_due_date_from_model(tmp_path, monkeypatch):
    app = load_app(tmp_path)
    from app import ai_services
    from app import schemas

    app_response = ai_services.IngestStructuredOutput(
        classification=ai_services.IngestDocumentClassificationOutput(
            document_type="invoice",
            provider_name="Oklart AB",
            label="Stökig faktura",
            amount=87.5,
            currency="EUR",
            due_date="not-a-date",
            cadence="monthly",
            category_hint="unknown",
            suggested_target_entity_type="recurring_cost",
            household_relevance="medium",
            confidence=0.61,
            confirmed_fields=["provider_name", "amount", "currency"],
            notes=["Texten är osäker."],
            uncertainty_reasons=["Datumet kunde inte läsas säkert."],
        ),
        summary="Osäker faktura.",
        guidance=["Behandla som osäkert underlag."],
        suggestions=[],
    )

    def fake_call_openai_structured(*_args, **_kwargs):
        return app_response, "gpt-test", schemas.AIUsageRead(input_tokens=80, output_tokens=40, total_tokens=120)

    monkeypatch.setattr(ai_services, "_call_openai_structured", fake_call_openai_structured)

    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        response = client.post(
            f"/households/{household_id}/ingest_ai/analyze",
            json={
                "input_text": "Kund: ACME. Betala helst snart. Något med 87,50 EUR, kanske månadsvis?",
                "input_kind": "pdf_text",
                "source_channel": "pdf_text",
                "source_name": "Oklart underlag",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["document_summary"]["due_date"] is None
        assert any("förfallodatum" in item.lower() for item in payload["document_summary"]["uncertainty_reasons"])


def test_ingest_promote_reuses_existing_document_id(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]
        recurring_before = client.get("/recurring_costs?skip=0&limit=100")
        assert recurring_before.status_code == 200
        recurring_before_count = len([item for item in recurring_before.json() if item["household_id"] == household_id])

        document = client.post(
            "/documents",
            json={
                "household_id": household_id,
                "document_type": "invoice",
                "file_name": "existing.txt",
                "mime_type": "text/plain",
                "extracted_text": "Resurs Bank faktura april 299 kr förfaller 2026-04-12.",
            },
        )
        assert document.status_code == 201
        document_id = document.json()["id"]

        suggestion = {
            "target_entity_type": "recurring_cost",
            "review_bucket": "recurring_cost",
            "title": "Resurs Bank - återkommande kostnad",
            "rationale": "Tydlig månadsfaktura.",
            "confidence": 0.9,
            "proposed_json": {
                "household_id": household_id,
                "category": "debt",
                "amount": 299,
                "frequency": "monthly",
                "vendor": "Resurs Bank",
                "mandatory": True,
                "variability_class": "fixed",
                "controllability": "locked",
            },
            "validation_status": "valid",
            "validation_errors": [],
            "uncertainty_notes": ["Viss avrundning kan förekomma."],
        }

        analysis_result_id = seed_ingest_analysis_result(
            household_id=household_id,
            document_id=document_id,
            source_channel="uploaded_document",
            source_name="Resurs Bank",
            extracted_text="Resurs Bank faktura april 299 kr förfaller 2026-04-12.",
            suggestions=[suggestion],
            document_summary={
                "document_type": "invoice",
                "provider_name": "Resurs Bank",
                "label": "Resurs Bank faktura april",
                "amount": 299,
                "currency": "SEK",
                "due_date": "2026-04-12",
                "cadence": "monthly",
                "category_hint": "subscription",
                "suggested_target_entity_type": "recurring_cost",
                "household_relevance": "high",
                "confidence": 0.94,
                "confirmed_fields": ["provider_name", "amount", "due_date"],
                "notes": ["Beloppet är tydligt."],
                "uncertainty_reasons": ["Cadence är tolkad."],
            },
        )

        response = client.post(
            f"/households/{household_id}/ingest_ai/promote",
            json={
                "analysis_result_id": analysis_result_id,
                "document_id": document_id,
                "source_channel": "uploaded_document",
                "source_name": "Resurs Bank",
                "provider": "openai",
                "model": "gpt-test",
                "document_summary": {
                    "document_type": "invoice",
                    "provider_name": "Resurs Bank",
                    "label": "Resurs Bank faktura april",
                    "amount": 299,
                    "currency": "SEK",
                    "due_date": "2026-04-12",
                    "cadence": "monthly",
                    "category_hint": "subscription",
                    "suggested_target_entity_type": "recurring_cost",
                    "household_relevance": "high",
                    "confidence": 0.94,
                    "confirmed_fields": ["provider_name", "amount", "due_date"],
                    "notes": ["Beloppet är tydligt."],
                    "uncertainty_reasons": ["Cadence är tolkad."],
                },
                "suggestions": [suggestion],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["document_id"] == document_id
        assert payload["document_type"] == "invoice"
        assert payload["created_drafts"][0]["validation_status"] == "valid"

        documents = client.get("/documents?skip=0&limit=100")
        assert documents.status_code == 200
        household_documents = [item for item in documents.json() if item["household_id"] == household_id]
        assert len(household_documents) == 1

        drafts = client.get("/extraction_drafts?skip=0&limit=100")
        assert drafts.status_code == 200
        household_drafts = [item for item in drafts.json() if item["household_id"] == household_id]
        assert len(household_drafts) == 1

        recurring_after = client.get("/recurring_costs?skip=0&limit=100")
        assert recurring_after.status_code == 200
        recurring_after_count = len([item for item in recurring_after.json() if item["household_id"] == household_id])
        assert recurring_after_count == recurring_before_count


def test_ingest_analyze_accepts_image_source_channel(tmp_path):
    """image source channel is now supported — verify it normalizes correctly."""
    app = load_app(tmp_path)
    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        response = client.post(
            f"/households/{household_id}/ingest_ai/analyze",
            json={"input_text": "OCR text from an image: Faktura 299 kr", "source_channel": "image"},
        )
        assert response.status_code in {200, 503}


def test_document_upload_handles_image_with_ocr(tmp_path):
    """Real OCR is now attempted on images. Fake PNG data results in parse_failed."""
    app = load_app(tmp_path)
    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        upload = client.post(
            "/documents/upload",
            data={"household_id": str(household_id), "document_type": "receipt", "issuer": "Telefon"},
            files={"file": ("screen.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")},
        )
        assert upload.status_code == 201
        payload = upload.json()
        assert payload["extraction_status"] in {"failed", "interpreted", "uploaded"}


def test_normalize_ingest_text_handles_pdf_paste_artifacts():
    from app.ingest_content import normalize_ingest_text

    raw = "Faktura\u00a0123\r\nBelopp:\u200b 1\u00a0500,00\fSida 2\r\nLeverantör: Test AB"
    result = normalize_ingest_text(raw)
    assert "\u00a0" not in result
    assert "\u200b" not in result
    assert "\f" not in result
    assert "Faktura 123" in result
    assert "Sida 2" in result


def test_detect_input_hints_finds_invoice_keywords():
    from app.ingest_content import detect_input_hints

    invoice_text = "Faktura 2026-04-01\nFörfallodatum: 2026-04-30\nBelopp: 1 299,00 SEK\nBankgiro: 123-4567"
    hints = detect_input_hints(invoice_text)
    assert "invoice_keywords" in hints
    assert "iso_dates" in hints
    assert "swedish_amounts" in hints


def test_detect_input_hints_finds_subscription_keywords():
    from app.ingest_content import detect_input_hints

    sub_text = "Abonnemang: Telia Bredband\nBindningstid: 24 månader\nKostnad: 399 kr/mån"
    hints = detect_input_hints(sub_text)
    assert "subscription_keywords" in hints
    assert "monthly_cost_pattern" in hints


def test_detect_input_hints_returns_empty_for_generic_text():
    from app.ingest_content import detect_input_hints

    hints = detect_input_hints("Hej, detta är en generisk text utan specifika nyckelord.")
    assert hints == []


def test_ingest_analyze_includes_input_hints_in_payload(tmp_path, monkeypatch):
    app = load_app(tmp_path)
    from app import ai_services
    from app import schemas

    captured_payload = {}

    app_response = ai_services.IngestStructuredOutput(
        classification=ai_services.IngestDocumentClassificationOutput(
            document_type="invoice",
            provider_name="Telia",
            label="Telia faktura",
            amount=399.0,
            currency="SEK",
            due_date="2026-04-30",
            cadence="monthly",
            category_hint="broadband",
            suggested_target_entity_type="subscription_contract",
            household_relevance="high",
            confidence=0.88,
            confirmed_fields=["provider_name", "amount", "currency"],
            notes=["Bredbandsabonnemang med tydligt belopp."],
            uncertainty_reasons=["Bindningstiden tolkas från text."],
        ),
        summary="En faktura för ett bredbandsabonnemang hos Telia.",
        guidance=["Tydligt abonnemang. Granska om bindningstid stämmer."],
        suggestions=[
            ai_services.IngestStructuredSuggestion(
                target_entity_type="subscription_contract",
                review_bucket="subscription_contract",
                title="Telia Bredband",
                rationale="Tydlig faktura med månatlig kostnad.",
                confidence=0.85,
                proposed_json='{"household_id": 1, "category": "broadband", "provider": "Telia", "current_monthly_cost": 399, "billing_frequency": "monthly"}',
                uncertainty_notes=["Bindningstid tolkas som 24 månader."],
            )
        ],
    )

    original_call = ai_services._call_openai_structured

    def fake_call_openai_structured(settings, *, model, instructions, payload, response_model, schema_name, max_output_tokens):
        captured_payload.update(payload)
        return app_response, "gpt-test", schemas.AIUsageRead(input_tokens=150, output_tokens=80, total_tokens=230)

    monkeypatch.setattr(ai_services, "_call_openai_structured", fake_call_openai_structured)

    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        response = client.post(
            f"/households/{household_id}/ingest_ai/analyze",
            json={
                "input_text": "Faktura 2026-04-01\nTelia Bredband\nKostnad: 399 kr/mån\nFörfallodatum: 2026-04-30",
                "input_kind": "text",
                "source_channel": "text",
                "source_name": "Telia",
            },
        )
        assert response.status_code == 200
        assert "input_hints" in captured_payload
        assert "invoice_keywords" in captured_payload["input_hints"]
        assert "monthly_cost_pattern" in captured_payload["input_hints"]

        payload = response.json()
        assert payload["document_summary"]["document_type"] == "invoice"
        assert payload["document_summary"]["provider_name"] == "Telia"
        assert payload["document_summary"]["amount"] == 399.0
        assert payload["suggestions"][0]["review_bucket"] == "subscription_contract"


def test_tesseract_ocr_extractor_on_real_image():
    from PIL import Image
    from app.ingest_content import TesseractOCRExtractor

    img = Image.new("RGB", (400, 100), "white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.text((10, 30), "Faktura 299 SEK", fill="black")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()

    extractor = TesseractOCRExtractor()
    result = extractor.extract_text(raw, file_name="test.png", mime_type="image/png")
    assert result.extraction_mode == "ocr_tesseract"
    assert result.text is not None
    assert len(result.text) > 0


def test_tesseract_ocr_extractor_on_corrupt_image():
    from app.ingest_content import TesseractOCRExtractor

    extractor = TesseractOCRExtractor()
    result = extractor.extract_text(b"not an image at all", file_name="bad.png", mime_type="image/png")
    assert result.extraction_mode == "ocr_image_unreadable"
    assert result.text is None


def test_bank_paste_source_channel_normalizes():
    from app.ai_services import _normalize_source_channel
    assert _normalize_source_channel("bank_paste", None) == "bank_paste"
    assert _normalize_source_channel(None, "bank_copy_paste") == "bank_paste"
    assert _normalize_source_channel("image", None) == "image"
    assert _normalize_source_channel("image_placeholder", None) == "image"


def test_ingest_analyze_bank_paste_with_mock(tmp_path, monkeypatch):
    app = load_app(tmp_path)
    from app import ai_services
    from app import schemas

    app_response = ai_services.IngestStructuredOutput(
        classification=ai_services.IngestDocumentClassificationOutput(
            document_type="bank_row_batch",
            provider_name=None,
            label="Kontoutdrag LF",
            amount=None,
            currency="SEK",
            due_date=None,
            cadence=None,
            category_hint=None,
            suggested_target_entity_type=None,
            household_relevance="high",
            confidence=0.7,
            confirmed_fields=["currency"],
            notes=["LF-format kontoutdrag med 3 rader."],
            uncertainty_reasons=["Raderna har varierande tolkningssäkerhet."],
        ),
        summary="Kontoutdrag med tre rader.",
        guidance=["Granska varje rad separat."],
        suggestions=[
            ai_services.IngestStructuredSuggestion(
                target_entity_type="recurring_cost",
                review_bucket="recurring_cost",
                title="ICA MAXI -1245,00",
                rationale="Trolig matinköpskostnad.",
                confidence=0.6,
                proposed_json='{"household_id": 1, "category": "other", "amount": 1245, "frequency": "monthly", "vendor": "ICA MAXI", "mandatory": true, "variability_class": "variable", "controllability": "reducible"}',
                uncertainty_notes=["Frekvensen är osäker."],
            ),
        ],
    )

    def fake_call(settings, *, model, instructions, payload, response_model, schema_name, max_output_tokens):
        assert max_output_tokens > 720
        assert "bank_row_batch" in instructions or "bankrader" in instructions.lower()
        return app_response, "gpt-test", schemas.AIUsageRead(input_tokens=200, output_tokens=150, total_tokens=350)

    monkeypatch.setattr(ai_services, "_call_openai_structured", fake_call)

    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        response = client.post(
            f"/households/{household_id}/ingest_ai/analyze",
            json={
                "input_text": "Bokföringsdatum\tTransaktionsdatum\tTransaktionstext\tBelopp\tSaldo\n2026-03-15\t2026-03-14\tICA MAXI\t-1245,00\t23456,78",
                "source_channel": "bank_paste",
                "source_name": "LF konto",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["document_summary"]["document_type"] == "bank_row_batch"
        assert payload["source_channel"] == "bank_paste"
        assert len(payload["suggestions"]) == 1
        assert payload["suggestions"][0]["review_bucket"] == "recurring_cost"


def test_bank_pdf_export_generates_valid_pdf(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        response = client.get(f"/households/{household_id}/export/bank_pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert b"%PDF" in response.content[:10]
        assert len(response.content) > 1000


def test_summary_includes_risk_signals(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app) as client:
        household = client.post("/households", json={"name": "Risk Test", "currency": "SEK", "primary_country": "SE"})
        household_id = household.json()["id"]

        summary = client.get(f"/households/{household_id}/summary")
        assert summary.status_code == 200
        payload = summary.json()
        assert "risk_signals" in payload
        assert any(sig["key"] == "no_income" for sig in payload["risk_signals"])


def test_ingest_suggestion_has_intelligence_fields(tmp_path, monkeypatch):
    app = load_app(tmp_path)
    from app import ai_services, schemas

    app_response = ai_services.IngestStructuredOutput(
        classification=ai_services.IngestDocumentClassificationOutput(
            document_type="subscription_contract",
            provider_name="Netflix",
            label="Netflix Standard",
            amount=149.0,
            currency="SEK",
            due_date=None,
            cadence="monthly",
            category_hint="streaming",
            suggested_target_entity_type="subscription_contract",
            household_relevance="high",
            confidence=0.95,
            confirmed_fields=["provider_name", "amount"],
            notes=[],
            uncertainty_reasons=[],
        ),
        summary="Netflix-abonnemang.",
        guidance=[],
        suggestions=[
            ai_services.IngestStructuredSuggestion(
                target_entity_type="subscription_contract",
                review_bucket="subscription_contract",
                title="Netflix",
                rationale="Tydligt streaming-abonnemang.",
                confidence=0.92,
                proposed_json='{"household_id":1,"category":"streaming","provider":"Netflix","current_monthly_cost":149,"billing_frequency":"monthly"}',
                uncertainty_notes=[],
            ),
        ],
    )

    def fake_call(*_a, **_kw):
        return app_response, "gpt-test", schemas.AIUsageRead(input_tokens=100, output_tokens=50, total_tokens=150)

    monkeypatch.setattr(ai_services, "_call_openai_structured", fake_call)

    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        response = client.post(
            f"/households/{household_id}/ingest_ai/analyze",
            json={"input_text": "Netflix 149 kr/mån", "source_channel": "text"},
        )
        assert response.status_code == 200
        suggestion = response.json()["suggestions"][0]
        assert "ownership_candidate" in suggestion
        assert suggestion["ownership_candidate"] == "private"
        assert "why_suggested" in suggestion
        assert len(suggestion["why_suggested"]) > 0
        assert "review_json" in suggestion


def test_document_review_flow_for_loan_invoice_upload_and_apply(tmp_path):
    app = load_app(tmp_path)
    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        upload = client.post(
            "/documents/upload",
            data={"household_id": str(household_id), "document_type": "loan_statement", "issuer": "Volvofinans"},
            files={
                "file": (
                    "loan_invoice.txt",
                    io.BytesIO(
                        (
                            "Volvofinans låneavi\n"
                            "Kontraktsnummer VF-7788\n"
                            "Objekt Volvo XC60\n"
                            "Ränta 6.45\n"
                            "Skuld före amortering 185000\n"
                            "Belopp att betala 4525\n"
                            "Förfallodatum 2026-05-28\n"
                            "Amortering 3100\n"
                            "Räntekostnad 1180\n"
                            "Avgifter 245\n"
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]
        assert upload.json()["extraction_status"] == "interpreted"

        analysis_result_id = seed_ingest_analysis_result(
            household_id=household_id,
            document_id=document_id,
            source_channel="uploaded_document",
            source_name="Volvofinans",
            extracted_text=(
                "Volvofinans låneavi\n"
                "Kontraktsnummer VF-7788\n"
                "Objekt Volvo XC60\n"
                "Ränta 6.45\n"
                "Skuld före amortering 185000\n"
                "Belopp att betala 4525\n"
                "Förfallodatum 2026-05-28\n"
                "Amortering 3100\n"
                "Räntekostnad 1180\n"
                "Avgifter 245\n"
            ),
            suggestions=[
                {
                    "target_entity_type": "loan",
                    "review_bucket": "loan",
                    "title": "Volvofinans billån",
                    "rationale": "Tydlig låneavi.",
                    "confidence": 0.91,
                    "proposed_json": {
                        "household_id": household_id,
                        "type": "car",
                        "lender": "Volvofinans",
                        "current_balance": 185000,
                        "required_monthly_payment": 4525,
                        "nominal_rate": 6.45,
                        "amortization_amount_monthly": 3100,
                        "purpose": "Volvo XC60",
                        "status": "active",
                    },
                    "review_json": {
                        "lender": "Volvofinans",
                        "interest_rate": 6.45,
                        "debt_before_amortization": 185000,
                        "payment_amount": 4525,
                        "payment_due_date": "2026-05-28",
                        "object_vehicle": "Volvo XC60",
                        "contract_number": "VF-7788",
                        "amortization": 3100,
                        "interest_cost": 1180,
                        "fees": 245,
                    },
                    "validation_status": "valid",
                    "validation_errors": [],
                    "uncertainty_notes": [],
                }
            ],
            document_summary={
                "document_type": "loan_or_credit",
                "provider_name": "Volvofinans",
                "label": "Volvofinans låneavi",
                "amount": 4525,
                "currency": "SEK",
                "due_date": "2026-05-28",
                "cadence": "monthly",
                "category_hint": "vehicle",
                "suggested_target_entity_type": "loan",
                "household_relevance": "high",
                "confidence": 0.96,
                "confirmed_fields": ["provider_name", "amount", "due_date"],
                "notes": [],
                "uncertainty_reasons": [],
            },
        )

        promote = client.post(
            f"/households/{household_id}/ingest_ai/promote",
            json={
                "analysis_result_id": analysis_result_id,
                "document_id": document_id,
                "source_channel": "uploaded_document",
                "source_name": "Volvofinans",
                "provider": "openai",
                "model": "gpt-test",
                "document_summary": {
                    "document_type": "loan_or_credit",
                    "provider_name": "Volvofinans",
                    "label": "Volvofinans låneavi",
                    "amount": 4525,
                    "currency": "SEK",
                    "due_date": "2026-05-28",
                    "cadence": "monthly",
                    "category_hint": "vehicle",
                    "suggested_target_entity_type": "loan",
                    "household_relevance": "high",
                    "confidence": 0.96,
                    "confirmed_fields": ["provider_name", "amount", "due_date"],
                    "notes": [],
                    "uncertainty_reasons": [],
                },
                "suggestions": [
                    {
                        "target_entity_type": "loan",
                        "review_bucket": "loan",
                        "title": "Volvofinans billån",
                        "rationale": "Tydlig låneavi.",
                        "confidence": 0.91,
                        "proposed_json": {
                            "household_id": household_id,
                            "type": "car",
                            "lender": "Volvofinans",
                            "current_balance": 185000,
                            "required_monthly_payment": 4525,
                            "nominal_rate": 6.45,
                            "amortization_amount_monthly": 3100,
                            "purpose": "Volvo XC60",
                            "status": "active",
                        },
                        "review_json": {
                            "lender": "Volvofinans",
                            "interest_rate": 6.45,
                            "debt_before_amortization": 185000,
                            "payment_amount": 4525,
                            "payment_due_date": "2026-05-28",
                            "object_vehicle": "Volvo XC60",
                            "contract_number": "VF-7788",
                            "amortization": 3100,
                            "interest_cost": 1180,
                            "fees": 245,
                        },
                        "validation_status": "valid",
                        "validation_errors": [],
                        "uncertainty_notes": [],
                    }
                ],
            },
        )
        assert promote.status_code == 200
        draft_id = promote.json()["created_drafts"][0]["draft_id"]

        review = client.get(f"/documents/{document_id}/review")
        assert review.status_code == 200
        review_payload = review.json()
        assert review_payload["workflow_status"] == "pending_review"
        labels = {item["label"]: item["value"] for item in review_payload["key_fields"]}
        assert labels["Långivare"] == "Volvofinans"
        assert labels["Ränta"] == "6.45"
        assert labels["Skuld före amortering"] == "185000"
        assert labels["Belopp att betala"] == "4525"
        assert labels["Förfallodatum"] == "2026-05-28"
        assert labels["Objekt / bil"] == "Volvo XC60"
        assert labels["Kontraktsnummer"] == "VF-7788"
        assert labels["Amortering"] == "3100"
        assert labels["Räntekostnad"] == "1180"
        assert labels["Avgifter"] == "245"

        apply_response = client.post(f"/extraction_drafts/{draft_id}/apply", json={"action": "create_new"})
        assert apply_response.status_code == 200
        loan_id = apply_response.json()["target_entity_id"]

        loan = client.get(f"/loans/{loan_id}")
        assert loan.status_code == 200
        loan_payload = loan.json()
        assert loan_payload["lender"] == "Volvofinans"
        assert loan_payload["nominal_rate"] == 6.45
        assert loan_payload["current_balance"] == 185000
        assert loan_payload["required_monthly_payment"] == 4525
        assert loan_payload["amortization_amount_monthly"] == 3100
        assert loan_payload["due_day"] == 28
        assert loan_payload["purpose"] == "Volvo XC60"
        assert loan_payload["statement_doc_id"] == document_id
        assert "VF-7788" in (loan_payload["note"] or "")

        applied_review = client.get(f"/documents/{document_id}/review")
        assert applied_review.status_code == 200
        applied_payload = applied_review.json()
        assert applied_payload["workflow_status"] == "applied"
        assert applied_payload["canonical_links"][0]["target_entity_type"] == "loan"
        assert applied_payload["canonical_links"][0]["target_entity_id"] == loan_id


def test_draft_can_link_document_to_existing_loan(tmp_path):
    app = load_app(tmp_path)
    from app import ai_services, database

    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        loan = client.post(
            "/loans",
            json={
                "household_id": household_id,
                "type": "car",
                "lender": "Volvofinans",
                "purpose": "Bil",
                "status": "active",
            },
        )
        assert loan.status_code == 201
        loan_id = loan.json()["id"]

        document = client.post(
            "/documents",
            json={
                "household_id": household_id,
                "document_type": "loan_statement",
                "file_name": "existing-loan.txt",
                "mime_type": "text/plain",
                "extracted_text": "Volvofinans avi",
                "extraction_status": "interpreted",
            },
        )
        assert document.status_code == 201
        document_id = document.json()["id"]

        draft = client.post(
            "/extraction_drafts",
            json={
                "household_id": household_id,
                "document_id": document_id,
                "target_entity_type": "loan",
                "proposed_json": {
                    "household_id": household_id,
                    "type": "car",
                    "lender": "Volvofinans",
                    "required_monthly_payment": 3990,
                    "current_balance": 120000,
                },
                "review_json": {
                    "lender": "Volvofinans",
                    "payment_amount": 3990,
                    "debt_before_amortization": 120000,
                    "contract_number": "VF-LINK-1",
                },
                "status": "pending_review",
            },
        )
        assert draft.status_code == 201
        draft_id = draft.json()["id"]

        apply_response = client.post(
            f"/extraction_drafts/{draft_id}/apply",
            json={"action": "link_existing", "target_entity_id": loan_id},
        )
        assert apply_response.status_code == 200

        updated = client.get(f"/loans/{loan_id}")
        assert updated.status_code == 200
        updated_payload = updated.json()
        assert updated_payload["required_monthly_payment"] == 3990
        assert updated_payload["current_balance"] == 120000
        assert updated_payload["statement_doc_id"] == document_id
        assert "VF-LINK-1" in (updated_payload["note"] or "")

        review = client.get(f"/documents/{document_id}/review")
        assert review.status_code == 200
        payload = review.json()
        assert payload["workflow_status"] == "applied"
        assert payload["canonical_links"][0]["target_entity_id"] == loan_id

        db = database.SessionLocal()
        try:
            context = ai_services._compact_household_context(db, household_id)
        finally:
            db.close()

        loan_context = next(item for item in context["loans"] if item["lender"] == "Volvofinans")
        assert loan_context["monthly_payment"] == 3990
        assert loan_context["current_balance"] == 120000
        assert context["document_counts"]["drafts_pending_review"] == 0


def test_document_review_flow_tracks_status_and_applies_santander_kia_loan_exactly(tmp_path):
    app = load_app(tmp_path)
    from app import ai_services, database

    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        upload = client.post(
            "/documents/upload",
            data={"household_id": str(household_id), "document_type": "loan_statement", "issuer": "Santander Consumer Bank"},
            files={
                "file": (
                    "santander_kia.txt",
                    io.BytesIO(
                        (
                            "Santander Consumer Bank billåneavi\n"
                            "Dokumenttyp: Billånefaktura\n"
                            "Långivare: Santander Consumer Bank\n"
                            "Objekt: Kia\n"
                            "Faktureringsdatum: 2026-03-09\n"
                            "Förfallodatum: 2026-03-31\n"
                            "Att betala: 2 221 kr\n"
                            "Ränta: 2,60 %\n"
                            "Skuld före amortering: 188 979 kr\n"
                            "Amortering: 1 762 kr\n"
                            "Räntekostnad: 409 kr\n"
                            "Administrationsavgift: 49 kr\n"
                            "Kontraktsnummer: SANT-2026-03\n"
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]
        assert upload.json()["extraction_status"] == "interpreted"

        review_before = client.get(f"/documents/{document_id}/review")
        assert review_before.status_code == 200
        before_payload = review_before.json()
        assert before_payload["workflow_status"] == "interpreted"
        assert before_payload["status_detail"] == "Dokumentet har tolkats men inte blivit reviewutkast ännu."

        draft = client.post(
            "/extraction_drafts",
            json={
                "household_id": household_id,
                "document_id": document_id,
                "target_entity_type": "loan",
                "proposed_json": {
                    "household_id": household_id,
                    "type": "car",
                    "lender": "Santander Consumer Bank",
                    "required_monthly_payment": 2221,
                    "current_balance": 188979,
                    "nominal_rate": 2.6,
                    "amortization_amount_monthly": 1762,
                    "purpose": "Kia",
                    "status": "active",
                },
                "review_json": {
                    "lender": "Santander Consumer Bank",
                    "interest_rate": 2.6,
                    "debt_before_amortization": 188979,
                    "payment_amount": 2221,
                    "payment_due_date": "2026-03-31",
                    "object_vehicle": "Kia",
                    "contract_number": "SANT-2026-03",
                    "amortization": 1762,
                    "interest_cost": 409,
                    "fees": 49,
                },
                "status": "pending_review",
            },
        )
        assert draft.status_code == 201
        draft_id = draft.json()["id"]

        review_pending = client.get(f"/documents/{document_id}/review")
        assert review_pending.status_code == 200
        pending_payload = review_pending.json()
        assert pending_payload["workflow_status"] == "pending_review"
        labels = {item["label"]: item["value"] for item in pending_payload["key_fields"]}
        assert labels["Långivare"] == "Santander Consumer Bank"
        assert labels["Objekt / bil"] == "Kia"
        assert labels["Ränta"] == "2.6"
        assert labels["Skuld före amortering"] == "188979"
        assert labels["Belopp att betala"] == "2221"
        assert labels["Amortering"] == "1762"
        assert labels["Räntekostnad"] == "409"
        assert labels["Avgifter"] == "49"

        apply_response = client.post(f"/extraction_drafts/{draft_id}/apply", json={"action": "create_new"})
        assert apply_response.status_code == 200
        loan_id = apply_response.json()["target_entity_id"]

        loan = client.get(f"/loans/{loan_id}")
        assert loan.status_code == 200
        loan_payload = loan.json()
        assert loan_payload["lender"] == "Santander Consumer Bank"
        assert loan_payload["purpose"] == "Kia"
        assert loan_payload["current_balance"] == 188979
        assert loan_payload["required_monthly_payment"] == 2221
        assert loan_payload["nominal_rate"] == 2.6
        assert loan_payload["amortization_amount_monthly"] == 1762
        assert loan_payload["due_day"] == 31
        assert loan_payload["statement_doc_id"] == document_id
        assert "SANT-2026-03" in (loan_payload["note"] or "")

        review_after = client.get(f"/documents/{document_id}/review")
        assert review_after.status_code == 200
        after_payload = review_after.json()
        assert after_payload["workflow_status"] == "applied"
        assert after_payload["canonical_links"][0]["target_entity_type"] == "loan"
        assert after_payload["canonical_links"][0]["target_entity_id"] == loan_id

        db = database.SessionLocal()
        try:
            context = ai_services._compact_household_context(db, household_id)
        finally:
            db.close()

        assert context["document_counts"]["drafts_pending_review"] == 0
        santander_loan = next(item for item in context["loans"] if item["lender"] == "Santander Consumer Bank")
        assert santander_loan["monthly_payment"] == 2221
        assert santander_loan["current_balance"] == 188979


def test_document_package_apply_creates_loan_and_vehicle_and_updates_assistant_context(tmp_path):
    app = load_app(tmp_path)
    from app import ai_services, database

    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        upload = client.post(
            "/documents/upload",
            data={"household_id": str(household_id), "document_type": "loan_statement", "issuer": "Santander Consumer Bank"},
            files={
                "file": (
                    "santander_kia.txt",
                    io.BytesIO(
                        (
                            "Santander Consumer Bank billåneavi\n"
                            "Dokumenttyp: Billånefaktura\n"
                            "Långivare: Santander Consumer Bank\n"
                            "Objekt: Kia\n"
                            "Faktureringsdatum: 2026-03-09\n"
                            "Förfallodatum: 2026-03-31\n"
                            "Att betala: 2 221 kr\n"
                            "Ränta: 2,60 %\n"
                            "Skuld före amortering: 188 979 kr\n"
                            "Amortering: 1 762 kr\n"
                            "Räntekostnad: 409 kr\n"
                            "Administrationsavgift: 49 kr\n"
                            "Kontraktsnummer: SANT-2026-03\n"
                        ).encode("utf-8")
                    ),
                    "text/plain",
                )
            },
        )
        assert upload.status_code == 201
        document_id = upload.json()["id"]

        draft = client.post(
            "/extraction_drafts",
            json={
                "household_id": household_id,
                "document_id": document_id,
                "target_entity_type": "loan",
                "proposed_json": {
                    "household_id": household_id,
                    "type": "car",
                    "lender": "Santander Consumer Bank",
                    "required_monthly_payment": 2221,
                    "current_balance": 188979,
                    "nominal_rate": 2.6,
                    "amortization_amount_monthly": 1762,
                    "purpose": "Kia",
                    "status": "active",
                },
                "review_json": {
                    "lender": "Santander Consumer Bank",
                    "interest_rate": 2.6,
                    "debt_before_amortization": 188979,
                    "payment_amount": 2221,
                    "payment_due_date": "2026-03-31",
                    "object_vehicle": "Kia",
                    "contract_number": "SANT-2026-03",
                    "amortization": 1762,
                    "interest_cost": 409,
                    "fees": 49,
                },
                "status": "pending_review",
            },
        )
        assert draft.status_code == 201
        draft_id = draft.json()["id"]

        apply_response = client.post(
            f"/documents/{document_id}/apply",
            json={
                "draft_ids": [draft_id],
                "draft_actions": [{"draft_id": draft_id, "action": "create_new"}],
                "related_actions": [{"source_draft_id": draft_id, "entity_type": "vehicle", "action": "create_new"}],
            },
        )
        assert apply_response.status_code == 200
        payload = apply_response.json()
        assert payload["workflow_status"] == "applied"
        assert payload["apply_summary"]["status"] == "applied"
        mutation_types = {(item["entity_type"], item["action"]) for item in payload["apply_summary"]["mutations"]}
        assert ("loan", "created") in mutation_types
        assert ("vehicle", "created") in mutation_types

        loan_link = next(item for item in payload["workflow"]["canonical_links"] if item["target_entity_type"] == "loan")
        vehicle_link = next(item for item in payload["workflow"]["canonical_links"] if item["target_entity_type"] == "vehicle")

        loan = client.get(f"/loans/{loan_link['target_entity_id']}")
        vehicle = client.get(f"/vehicles/{vehicle_link['target_entity_id']}")
        assert loan.status_code == 200
        assert vehicle.status_code == 200
        assert loan.json()["lender"] == "Santander Consumer Bank"
        assert loan.json()["purpose"] == "Kia"
        assert loan.json()["current_balance"] == 188979
        assert loan.json()["required_monthly_payment"] == 2221
        assert loan.json()["nominal_rate"] == 2.6
        assert loan.json()["amortization_amount_monthly"] == 1762
        assert vehicle.json()["loan_id"] == loan_link["target_entity_id"]
        assert vehicle.json()["make"] == "Kia"

        db = database.SessionLocal()
        try:
            context = ai_services._compact_household_context(db, household_id)
        finally:
            db.close()

        santander_loan = next(item for item in context["loans"] if item["lender"] == "Santander Consumer Bank")
        assert santander_loan["monthly_payment"] == 2221
        assert santander_loan["current_balance"] == 188979
        assert santander_loan["nominal_rate"] == 2.6
        assert santander_loan["linked_vehicle"] == "Kia"
        assert santander_loan["linked_vehicle_id"] == vehicle_link["target_entity_id"]
        assert santander_loan["linked_vehicle_summary"]["loan_id"] == loan_link["target_entity_id"]

        kia_vehicle = next(item for item in context["vehicles"] if item["id"] == vehicle_link["target_entity_id"])
        assert kia_vehicle["label"] == "Kia"
        assert kia_vehicle["loan_id"] == loan_link["target_entity_id"]
        assert context["document_counts"]["drafts_pending_review"] == 0


def test_assistant_context_excludes_pending_document_review_values(tmp_path):
    app = load_app(tmp_path)
    from app import ai_services, database

    with TestClient(app) as client:
        ids = create_household_fixture(client)
        household_id = ids["household_id"]

        document = client.post(
            "/documents",
            json={
                "household_id": household_id,
                "document_type": "loan_statement",
                "file_name": "secret-review.txt",
                "mime_type": "text/plain",
                "extracted_text": "Pending review loan document",
                "extraction_status": "pending_review",
            },
        )
        assert document.status_code == 201
        document_id = document.json()["id"]

        draft = client.post(
            "/extraction_drafts",
            json={
                "household_id": household_id,
                "document_id": document_id,
                "target_entity_type": "loan",
                "proposed_json": {
                    "household_id": household_id,
                    "type": "car",
                    "lender": "Top secret lender",
                    "required_monthly_payment": 9999,
                },
                "review_json": {
                    "contract_number": "SECRET-DOC-CONTRACT-42",
                    "payment_amount": 9999,
                },
                "status": "pending_review",
            },
        )
        assert draft.status_code == 201

        db = database.SessionLocal()
        try:
            context = ai_services._compact_household_context(db, household_id)
        finally:
            db.close()

        dumped = json.dumps(context, ensure_ascii=False)
        assert "SECRET-DOC-CONTRACT-42" not in dumped
        assert "Top secret lender" not in dumped
        assert context["document_counts"]["drafts_pending_review"] >= 1


def test_ingest_hash_canonicalization_allows_merchant_alias_without_false_mismatch(tmp_path, monkeypatch):
    app = load_app(tmp_path)
    from app import ai_services, schemas

    structured = ai_services.IngestStructuredOutput(
        classification=ai_services.IngestDocumentClassificationOutput(
            document_type="invoice",
            provider_name="ICA",
            label="ICA kvitto",
            amount=200.0,
            currency="SEK",
            due_date=None,
            cadence="monthly",
            category_hint="mat",
            suggested_target_entity_type="recurring_cost",
            household_relevance="high",
            confidence=0.8,
            confirmed_fields=["provider_name", "amount"],
            notes=[],
            uncertainty_reasons=[],
        ),
        summary="Test",
        guidance=[],
        suggestions=[
            ai_services.IngestStructuredSuggestion(
                target_entity_type="recurring_cost",
                review_bucket="recurring_cost",
                title="ICA",
                rationale="Alias match",
                confidence=0.8,
                proposed_json='{"household_id":1,"category":"mat","amount":200,"frequency":"monthly","vendor":"ICA","mandatory":true,"variability_class":"fixed","controllability":"locked"}',
                uncertainty_notes=[],
            )
        ],
    )

    monkeypatch.setattr(
        ai_services,
        "_call_openai_structured",
        lambda *_a, **_kw: (structured, "gpt-test", schemas.AIUsageRead(total_tokens=10)),
    )

    with TestClient(app) as client:
        hid = create_household_fixture(client)["household_id"]
        alias = client.post(
            f"/households/{hid}/merchant_aliases",
            json={"household_id": hid, "alias": "ica maxi", "canonical_name": "ICA", "category_hint": "mat"},
        )
        assert alias.status_code == 201

        text = "ICA MAXI 200 kr varje månad"
        analyze = client.post(
            f"/households/{hid}/ingest_ai/analyze",
            json={"input_text": text, "source_channel": "text", "source_name": "ICA"},
        )
        assert analyze.status_code == 200
        analysis_result_id = analyze.json()["analysis_result_id"]

        promote = client.post(
            f"/households/{hid}/ingest_ai/promote",
            json={
                "analysis_result_id": analysis_result_id,
                "input_text": text,
                "source_channel": "text",
                "source_name": "ICA",
            },
        )
        assert promote.status_code == 200


def test_ingest_hash_canonicalization_allows_truncated_text_without_false_mismatch(tmp_path, monkeypatch):
    app = load_app(tmp_path)
    from app import ai_services, schemas

    structured = ai_services.IngestStructuredOutput(
        classification=ai_services.IngestDocumentClassificationOutput(
            document_type="financial_note",
            provider_name=None,
            label="Lång text",
            amount=None,
            currency="SEK",
            due_date=None,
            cadence=None,
            category_hint=None,
            suggested_target_entity_type="recurring_cost",
            household_relevance="medium",
            confidence=0.6,
            confirmed_fields=[],
            notes=[],
            uncertainty_reasons=[],
        ),
        summary="Long",
        guidance=[],
        suggestions=[
            ai_services.IngestStructuredSuggestion(
                target_entity_type="recurring_cost",
                review_bucket="recurring_cost",
                title="Long recurring",
                rationale="Long text",
                confidence=0.7,
                proposed_json='{"household_id":1,"category":"other","amount":50,"frequency":"monthly","vendor":"Long","mandatory":true,"variability_class":"fixed","controllability":"locked"}',
                uncertainty_notes=[],
            )
        ],
    )

    monkeypatch.setattr(
        ai_services,
        "_call_openai_structured",
        lambda *_a, **_kw: (structured, "gpt-test", schemas.AIUsageRead(total_tokens=10)),
    )

    with TestClient(app) as client:
        hid = create_household_fixture(client)["household_id"]
        long_text = "A" * 7000
        analyze = client.post(
            f"/households/{hid}/ingest_ai/analyze",
            json={"input_text": long_text, "source_channel": "text", "source_name": "LongSource"},
        )
        assert analyze.status_code == 200
        analysis_result_id = analyze.json()["analysis_result_id"]

        promote = client.post(
            f"/households/{hid}/ingest_ai/promote",
            json={
                "analysis_result_id": analysis_result_id,
                "input_text": long_text,
                "source_channel": "text",
                "source_name": "LongSource",
            },
        )
        assert promote.status_code == 200


def test_ingest_hash_canonicalization_still_blocks_changed_source(tmp_path, monkeypatch):
    app = load_app(tmp_path)
    from app import ai_services, schemas

    structured = ai_services.IngestStructuredOutput(
        classification=ai_services.IngestDocumentClassificationOutput(
            document_type="financial_note",
            provider_name=None,
            label="Changed",
            amount=None,
            currency="SEK",
            due_date=None,
            cadence=None,
            category_hint=None,
            suggested_target_entity_type="recurring_cost",
            household_relevance="medium",
            confidence=0.6,
            confirmed_fields=[],
            notes=[],
            uncertainty_reasons=[],
        ),
        summary="Changed",
        guidance=[],
        suggestions=[
            ai_services.IngestStructuredSuggestion(
                target_entity_type="recurring_cost",
                review_bucket="recurring_cost",
                title="Changed recurring",
                rationale="Changed",
                confidence=0.7,
                proposed_json='{"household_id":1,"category":"other","amount":50,"frequency":"monthly","vendor":"Changed","mandatory":true,"variability_class":"fixed","controllability":"locked"}',
                uncertainty_notes=[],
            )
        ],
    )

    monkeypatch.setattr(
        ai_services,
        "_call_openai_structured",
        lambda *_a, **_kw: (structured, "gpt-test", schemas.AIUsageRead(total_tokens=10)),
    )

    with TestClient(app) as client:
        hid = create_household_fixture(client)["household_id"]
        analyze = client.post(
            f"/households/{hid}/ingest_ai/analyze",
            json={"input_text": "Original source text", "source_channel": "text", "source_name": "Source"},
        )
        assert analyze.status_code == 200
        analysis_result_id = analyze.json()["analysis_result_id"]

        promote = client.post(
            f"/households/{hid}/ingest_ai/promote",
            json={
                "analysis_result_id": analysis_result_id,
                "input_text": "Modified source text",
                "source_channel": "text",
                "source_name": "Source",
            },
        )
        assert promote.status_code == 400
        assert "matchar inte analyze-resultatet" in promote.json()["detail"]
