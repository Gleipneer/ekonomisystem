import pytest
import os
import importlib
from fastapi.testclient import TestClient

def load_app(tmp_path):
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["UPLOAD_DIR"] = str(tmp_path / "uploads")
    os.environ["AUTO_CREATE_SCHEMA"] = "true"
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

    return main.app, database.SessionLocal()

def create_local_household(client: TestClient) -> int:
    resp = client.post("/households", json={"name": "Test Household", "currency": "SEK", "primary_country": "SE"})
    return resp.json()["id"]


def create_source_message(db, client: TestClient, household_id: int, intent: str, data: dict, target_entity_type: str | None = None, missing_fields: list[str] | None = None):
    from app import models

    client.get(f"/households/{household_id}/assistant/thread")
    thread = db.query(models.ChatThread).filter_by(household_id=household_id, is_active=True).first()
    source_message = models.ChatMessage(
        thread_id=thread.id,
        role="assistant",
        message_type="assistant_response",
        content_text="Förslag",
        content_json={
            "write_intent": {
                "intent": intent,
                "target_entity_type": target_entity_type,
                "data": data,
                "missing_fields": missing_fields or [],
                "ambiguities": [],
                "confidence": 0.9,
            }
        },
    )
    db.add(source_message)
    db.commit()
    db.refresh(source_message)
    return source_message


def test_apply_requires_persisted_source_message(tmp_path):
    app, db = load_app(tmp_path)
    with TestClient(app) as client:
        hid = create_local_household(client)
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "create_expense",
                "data": {
                    "category": "Mat",
                    "vendor": "ICA",
                    "amount": 400.0,
                    "frequency": "monthly"
                }
            }
        )
        assert resp.status_code == 400
        assert "source_message_id" in resp.json()["detail"]
        db.close()


def test_apply_create_expense_from_persisted_write_intent(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        source_message = create_source_message(
            db,
            client,
            hid,
            "create_expense",
            {"category": "Mat", "vendor": "ICA", "amount": 400.0, "frequency": "monthly"},
            "recurring_cost",
        )
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "create_expense",
                "source_message_id": source_message.id,
                "data": {
                    "category": "Mat",
                    "vendor": "ICA",
                    "amount": 400.0,
                    "frequency": "monthly"
                }
            }
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        
        cost = db.query(models.RecurringCost).filter_by(household_id=hid).first()
        assert cost is not None
        assert cost.vendor == "ICA"
        assert cost.amount == 400.0
        db.close()


def test_apply_with_source_message_only_uses_stored_intent(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        source_message = create_source_message(
            db,
            client,
            hid,
            "create_expense",
            {"category": "Boende", "vendor": "Hyresvärd", "amount": 10000.0, "frequency": "monthly"},
            "recurring_cost",
        )
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={"source_message_id": source_message.id},
        )
        assert resp.status_code == 200
        cost = db.query(models.RecurringCost).filter_by(household_id=hid).first()
        assert cost is not None
        assert cost.amount == 10000.0
        assert cost.vendor == "Hyresvärd"
        db.close()


def test_apply_rejects_replay_of_already_applied_write_intent(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        source_message = create_source_message(
            db,
            client,
            hid,
            "create_expense",
            {"category": "Mat", "vendor": "ICA", "amount": 400.0, "frequency": "monthly"},
            "recurring_cost",
        )
        payload = {
            "intent": "create_expense",
            "source_message_id": source_message.id,
            "data": {
                "category": "Mat",
                "vendor": "ICA",
                "amount": 400.0,
                "frequency": "monthly",
            },
        }

        first = client.post(f"/households/{hid}/assistant/apply_intent", json=payload)
        second = client.post(f"/households/{hid}/assistant/apply_intent", json=payload)

        assert first.status_code == 200
        assert second.status_code == 409
        assert "redan applicerats" in second.json()["detail"]
        assert db.query(models.RecurringCost).filter_by(household_id=hid).count() == 1
        db.close()


def test_apply_rejects_empty_stored_data_mismatch(tmp_path):
    app, db = load_app(tmp_path)
    with TestClient(app) as client:
        hid = create_local_household(client)
        source_message = create_source_message(
            db,
            client,
            hid,
            "create_expense",
            {},
            "recurring_cost",
        )

        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "create_expense",
                "source_message_id": source_message.id,
                "data": {"category": "Mat", "amount": 400.0, "frequency": "monthly"},
            },
        )

        assert resp.status_code == 409
        assert "ändrats" in resp.json()["detail"]
        db.close()


def test_apply_rejects_non_assistant_source_message(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        client.get(f"/households/{hid}/assistant/thread")
        thread = db.query(models.ChatThread).filter_by(household_id=hid, is_active=True).first()
        source_message = models.ChatMessage(
            thread_id=thread.id,
            role="system",
            message_type="system_confirmation",
            content_text="Inte ett assistantsvar",
            content_json={
                "write_intent": {
                    "intent": "create_expense",
                    "target_entity_type": "recurring_cost",
                    "data": {"category": "Mat", "amount": 400.0, "frequency": "monthly"},
                    "missing_fields": [],
                },
            },
        )
        db.add(source_message)
        db.commit()
        db.refresh(source_message)

        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "create_expense",
                "source_message_id": source_message.id,
                "data": {"category": "Mat", "amount": 400.0, "frequency": "monthly"},
            },
        )

        assert resp.status_code == 404
        db.close()


def test_apply_rejects_incomplete_create_intent_even_without_missing_fields(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        source_message = create_source_message(
            db,
            client,
            hid,
            "create_subscription",
            {"provider": "Telia", "category": "mobile"},
            "subscription_contract",
        )

        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "create_subscription",
                "source_message_id": source_message.id,
                "target_entity_type": "subscription_contract",
                "data": {"provider": "Telia", "category": "mobile"},
            },
        )

        assert resp.status_code == 400
        assert "obligatoriska fält" in resp.json()["detail"]
        assert db.query(models.SubscriptionContract).filter_by(household_id=hid).count() == 0
        db.close()


def test_apply_rejects_write_intent_with_missing_fields(tmp_path):
    app, db = load_app(tmp_path)
    with TestClient(app) as client:
        hid = create_local_household(client)
        source_message = create_source_message(
            db,
            client,
            hid,
            "create_subscription",
            {"provider": "Telia", "category": "mobile"},
            "subscription_contract",
            missing_fields=["amount", "frequency"],
        )
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "create_subscription",
                "source_message_id": source_message.id,
                "target_entity_type": "subscription_contract",
                "data": {"provider": "Telia", "category": "mobile"},
            },
        )
        assert resp.status_code == 409
        assert "saknar" in resp.json()["detail"]
        db.close()


def test_apply_update_entity(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        cost = models.RecurringCost(
            household_id=hid,
            category="Test",
            vendor="Old Vendor",
            amount=100.0,
            frequency="monthly",
            status="active"
        )
        db.add(cost)
        db.commit()
        db.refresh(cost)
        cost_id = cost.id
        source_message = create_source_message(
            db,
            client,
            hid,
            "update_entity",
            {
                "entity_type": "recurring_cost",
                "entity_id": cost_id,
                "updates": {"vendor": "New Vendor", "amount": 200.0},
            },
            "recurring_cost",
        )
        
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "update_entity",
                "target_entity_type": "recurring_cost",
                "source_message_id": source_message.id,
                "data": {
                    "id": cost_id,
                    "vendor": "New Vendor",
                    "amount": 200.0
                }
            }
        )
        assert resp.status_code == 200
        db.refresh(cost)
        assert cost.vendor == "New Vendor"
        assert cost.amount == 200.0
        db.close()


def test_apply_update_entity_resolves_single_match(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        cost = models.RecurringCost(
            household_id=hid,
            category="boende",
            vendor="Hyra",
            amount=12500.0,
            frequency="monthly",
            status="active",
        )
        db.add(cost)
        db.commit()
        source_message = create_source_message(
            db,
            client,
            hid,
            "update_entity",
            {
                "match": {"category": "boende", "status": "active"},
                "updates": {"monthly_amount": 10000.0},
            },
            "recurring_cost",
        )
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={"source_message_id": source_message.id},
        )
        assert resp.status_code == 200
        db.refresh(cost)
        assert cost.amount == 10000.0
        db.close()


def test_apply_update_entity_match_ambiguous_is_blocked(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        db.add(models.RecurringCost(household_id=hid, category="boende", vendor="Hyra A", amount=12000.0, frequency="monthly", status="active"))
        db.add(models.RecurringCost(household_id=hid, category="boende", vendor="Hyra B", amount=12500.0, frequency="monthly", status="active"))
        db.commit()
        source_message = create_source_message(
            db,
            client,
            hid,
            "update_entity",
            {
                "match": {"category": "boende", "status": "active"},
                "updates": {"monthly_amount": 10000.0},
            },
            "recurring_cost",
        )
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={"source_message_id": source_message.id},
        )
        assert resp.status_code == 409
        assert "flera entiteter" in resp.json()["detail"]
        db.close()


def test_apply_update_entity_missing_fields_still_blocked(tmp_path):
    app, db = load_app(tmp_path)
    with TestClient(app) as client:
        hid = create_local_household(client)
        source_message = create_source_message(
            db,
            client,
            hid,
            "update_entity",
            {"match": {"category": "boende"}},
            "recurring_cost",
        )
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={"source_message_id": source_message.id},
        )
        assert resp.status_code == 400
        assert "saknar updates" in resp.json()["detail"].lower()
        db.close()

def test_apply_delete_entity(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        purchase = models.PlannedPurchase(
            household_id=hid,
            title="To be deleted",
            estimated_amount=1000.0,
            priority="optional",
            status="planned"
        )
        db.add(purchase)
        db.commit()
        db.refresh(purchase)
        p_id = purchase.id
        source_message = create_source_message(
            db,
            client,
            hid,
            "delete_entity",
            {
                "entity_type": "planned_purchase",
                "entity_id": p_id,
            },
            "planned_purchase",
        )
        
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "delete_entity",
                "target_entity_type": "planned_purchase",
                "source_message_id": source_message.id,
                "data": {
                    "id": p_id
                }
            }
        )
        assert resp.status_code == 200
        deleted = db.query(models.PlannedPurchase).filter_by(id=p_id).first()
        assert deleted is None
        db.close()


def test_apply_create_income_links_to_household_person(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        person = models.Person(household_id=hid, name="Anna", role="self", income_share_mode="pooled", active=True)
        db.add(person)
        db.commit()
        db.refresh(person)
        source_message = create_source_message(
            db,
            client,
            hid,
            "create_income",
            {
                "person_id": person.id,
                "source": "Lön",
                "amount": 25000.0,
                "frequency": "monthly",
                "type": "salary",
            },
            "income_source",
        )

        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "create_income",
                "source_message_id": source_message.id,
                "data": {
                    "person_id": person.id,
                    "source": "Lön",
                    "amount": 25000.0,
                    "frequency": "monthly",
                    "type": "salary",
                }
            }
        )
        assert resp.status_code == 200
        income = db.query(models.IncomeSource).filter_by(person_id=person.id).first()
        assert income is not None
        assert income.net_amount == 25000.0
        db.close()


def test_apply_rejects_source_message_mismatch(tmp_path):
    app, db = load_app(tmp_path)
    from app import models
    with TestClient(app) as client:
        hid = create_local_household(client)
        client.get(f"/households/{hid}/assistant/thread")
        thread = db.query(models.ChatThread).filter_by(household_id=hid, is_active=True).first()
        source_message = models.ChatMessage(
            thread_id=thread.id,
            role="assistant",
            message_type="assistant_response",
            content_text="Förslag",
            content_json={
                "write_intent": {
                    "intent": "create_expense",
                    "target_entity_type": "recurring_cost",
                    "data": {"vendor": "ICA", "amount": 400.0, "frequency": "monthly", "category": "Mat"},
                }
            },
        )
        db.add(source_message)
        db.commit()
        db.refresh(source_message)

        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "intent": "create_expense",
                "source_message_id": source_message.id,
                "data": {
                    "vendor": "Hemkop",
                    "amount": 400.0,
                    "frequency": "monthly",
                    "category": "Mat",
                }
            }
        )
        assert resp.status_code == 409
        assert "ändrats" in resp.json()["detail"]
        db.close()


def test_apply_rejects_manipulated_client_payload_even_with_valid_source(tmp_path):
    app, db = load_app(tmp_path)
    with TestClient(app) as client:
        hid = create_local_household(client)
        source_message = create_source_message(
            db,
            client,
            hid,
            "create_expense",
            {"vendor": "ICA", "amount": 400.0, "frequency": "monthly", "category": "Mat"},
            "recurring_cost",
        )
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={
                "source_message_id": source_message.id,
                "intent": "create_expense",
                "data": {"vendor": "Manipulerad", "amount": 100.0, "frequency": "monthly", "category": "Mat"},
            },
        )
        assert resp.status_code == 409
        assert "ändrats" in resp.json()["detail"]
        db.close()


def test_apply_blocks_batch_multi_update_without_contract(tmp_path):
    app, db = load_app(tmp_path)
    with TestClient(app) as client:
        hid = create_local_household(client)
        source_message = create_source_message(
            db,
            client,
            hid,
            "update_entity",
            {
                "proposed_updates": [
                    {"entity_type": "recurring_cost", "entity_id": 1, "updates": {"amount": 10000}},
                    {"entity_type": "loan", "entity_id": 2, "updates": {"required_monthly_payment": 2323}},
                ]
            },
            "recurring_cost",
        )
        resp = client.post(
            f"/households/{hid}/assistant/apply_intent",
            json={"source_message_id": source_message.id},
        )
        assert resp.status_code == 409
        assert "Batch-apply" in resp.json()["detail"]
        db.close()
