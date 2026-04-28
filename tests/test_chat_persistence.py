import importlib
import os

from fastapi.testclient import TestClient


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

    import app.ai_services as ai_services
    import app.database as database
    import app.import_services as import_services
    import app.main as main
    import app.models as models
    import app.schemas as schemas

    importlib.reload(ai_services)
    importlib.reload(import_services)
    importlib.reload(database)
    importlib.reload(models)
    importlib.reload(schemas)
    main = importlib.reload(main)

    return main.app, main, database, models


def create_local_household(client: TestClient) -> int:
    resp = client.post("/households", json={"name": "Test Household", "currency": "SEK", "primary_country": "SE"})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_assistant_messages_persist_with_structured_payload(tmp_path, monkeypatch):
    app, main, database, models = load_app(tmp_path)

    def fake_generate_analysis_answer(db, household_id, prompt, conversation, settings):
        return (
            "Här är svaret.",
            ["Vilken månad gäller det?"],
            main.schemas.AssistantWriteIntentRead(
                intent="create_expense",
                confidence=0.93,
                data={"vendor": "ICA", "amount": 400.0, "frequency": "monthly", "category": "Mat"},
                missing_fields=[],
                ambiguities=[],
            ),
            "gpt-test",
            main.schemas.AIUsageRead(input_tokens=11, output_tokens=7, total_tokens=18),
        )

    monkeypatch.setattr(main.ai_services, "generate_analysis_answer", fake_generate_analysis_answer)

    with TestClient(app) as client:
        household_id = create_local_household(client)

        resp = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "Lägg till ICA 400 kr varje månad", "conversation": []},
        )
        assert resp.status_code == 200

        thread_resp = client.get(f"/households/{household_id}/assistant/thread")
        assert thread_resp.status_code == 200
        thread = thread_resp.json()

    assert len(thread["messages"]) == 2
    assert thread["messages"][0]["role"] == "user"
    assert thread["messages"][0]["message_type"] == "user_prompt"
    assert thread["messages"][0]["content_text"] == "Lägg till ICA 400 kr varje månad"

    assert thread["messages"][1]["role"] == "assistant"
    assert thread["messages"][1]["message_type"] == "assistant_response"
    assert thread["messages"][1]["content_text"] == "Här är svaret."
    assert thread["messages"][1]["content_json"]["questions"] == ["Vilken månad gäller det?"]
    assert thread["messages"][1]["content_json"]["write_intent"]["intent"] == "create_expense"
    assert thread["messages"][1]["content_json"]["write_intent"]["data"]["vendor"] == "ICA"
    assert thread["messages"][1]["content_json"]["provider"] == "openai"
    assert thread["messages"][1]["content_json"]["model"] == "gpt-test"
    assert thread["messages"][1]["content_json"]["usage"]["total_tokens"] == 18

    db = database.SessionLocal()
    try:
        stored_messages = db.query(models.ChatMessage).order_by(models.ChatMessage.id.asc()).all()
        assert [message.role for message in stored_messages] == ["user", "assistant"]
        assert stored_messages[1].message_type == "assistant_response"
    finally:
        db.close()


def test_reload_returns_same_active_thread_and_messages(tmp_path, monkeypatch):
    app, main, _database, _models = load_app(tmp_path)

    def fake_generate_analysis_answer(db, household_id, prompt, conversation, settings):
        return ("Reload-safe answer", [], None, "gpt-test", main.schemas.AIUsageRead(total_tokens=5))

    monkeypatch.setattr(main.ai_services, "generate_analysis_answer", fake_generate_analysis_answer)

    with TestClient(app) as client:
        household_id = create_local_household(client)
        first_thread = client.get(f"/households/{household_id}/assistant/thread").json()
        client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "Hej igen", "conversation": []},
        )

    with TestClient(app) as client:
        second_thread = client.get(f"/households/{household_id}/assistant/thread")
        assert second_thread.status_code == 200
        thread = second_thread.json()

    assert thread["id"] == first_thread["id"]
    assert thread["is_active"] is True
    assert [message["content_text"] for message in thread["messages"]] == ["Hej igen", "Reload-safe answer"]


def test_assistant_uses_persisted_thread_context_not_client_conversation(tmp_path, monkeypatch):
    app, main, _database, _models = load_app(tmp_path)
    seen_conversations = []

    def fake_generate_analysis_answer(db, household_id, prompt, conversation, settings):
        seen_conversations.append([(message.role, message.content) for message in conversation])
        if len(seen_conversations) == 1:
            return ("Första svaret", [], None, "gpt-test", main.schemas.AIUsageRead(total_tokens=5))
        return ("Andra svaret", [], None, "gpt-test", main.schemas.AIUsageRead(total_tokens=5))

    monkeypatch.setattr(main.ai_services, "generate_analysis_answer", fake_generate_analysis_answer)

    with TestClient(app) as client:
        household_id = create_local_household(client)
        first = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "Första frågan", "conversation": []},
        )
        assert first.status_code == 200

        second = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "Andra frågan", "conversation": [{"role": "user", "content": "Falsk klienthistorik"}]},
        )
        assert second.status_code == 200

    assert seen_conversations[0] == []
    assert seen_conversations[1] == [
        ("user", "Första frågan"),
        ("assistant", "Första svaret"),
    ]


def test_apply_intent_persists_system_confirmation(tmp_path):
    app, _main, database, models = load_app(tmp_path)

    with TestClient(app) as client:
        household_id = create_local_household(client)
        client.get(f"/households/{household_id}/assistant/thread")

        database_session = database.SessionLocal()
        try:
            thread = database_session.query(models.ChatThread).filter_by(household_id=household_id, is_active=True).first()
            database_session.add(
                models.ChatMessage(
                    thread_id=thread.id,
                    role="assistant",
                    message_type="assistant_response",
                    content_text="Föreslagen åtgärd",
                    content_json={
                        "write_intent": {
                            "intent": "create_expense",
                            "data": {"vendor": "ICA", "amount": 400.0, "frequency": "monthly", "category": "Mat"},
                        }
                    },
                )
            )
            database_session.commit()
            source_message = database_session.query(models.ChatMessage).order_by(models.ChatMessage.id.desc()).first()
            source_message_id = source_message.id
        finally:
            database_session.close()

        resp = client.post(
            f"/households/{household_id}/assistant/apply_intent",
            json={
                "intent": "create_expense",
                "data": {"vendor": "ICA", "amount": 400.0, "frequency": "monthly", "category": "Mat"},
                "source_message_id": source_message_id,
            },
        )
        assert resp.status_code == 200

        thread_resp = client.get(f"/households/{household_id}/assistant/thread")
        assert thread_resp.status_code == 200
        messages = thread_resp.json()["messages"]

    assert messages[-1]["role"] == "system"
    assert messages[-1]["message_type"] == "system_confirmation"
    assert messages[-1]["content_json"]["applied"] is True
    assert messages[-1]["content_json"]["source_message_id"] == source_message_id
    assert messages[-1]["content_json"]["intent"] == "create_expense"
    assert messages[-1]["content_json"]["result"]["entity_type"] == "recurring_cost"


def test_import_handled_response_persists_system_message(tmp_path, monkeypatch):
    app, main, _database, _models = load_app(tmp_path)

    monkeypatch.setattr(
        main.import_services,
        "maybe_handle_assistant_prompt",
        lambda db, household_id, prompt: (True, "Paketet skickades till dokumentflödet.", "import-package-v1"),
    )

    with TestClient(app) as client:
        household_id = create_local_household(client)
        resp = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "ECON_IMPORT_PACKAGE_V1 ...", "conversation": []},
        )
        assert resp.status_code == 200

        thread_resp = client.get(f"/households/{household_id}/assistant/thread")
        assert thread_resp.status_code == 200
        messages = thread_resp.json()["messages"]

    assert [message["role"] for message in messages] == ["user", "system"]
    assert messages[1]["message_type"] == "system_import_notice"
    assert messages[1]["content_text"] == "Paketet skickades till dokumentflödet."
    assert messages[1]["content_json"]["provider"] == "system"
    assert messages[1]["content_json"]["model"] == "import-package-v1"


def test_assistant_chat_contract_for_normal_complete_and_incomplete_prompts(tmp_path, monkeypatch):
    app, main, database, models = load_app(tmp_path)

    def fake_generate_analysis_answer(db, household_id, prompt, conversation, settings):
        if "sammanfatta" in prompt.lower():
            return (
                "Det här är en sammanfattning av din ekonomi.",
                [],
                None,
                "gpt-test",
                main.schemas.AIUsageRead(total_tokens=10),
            )
        if "netflix" in prompt.lower():
            return (
                "Jag kan lägga till Netflix som abonnemang. Bekräfta genom apply.",
                [],
                main.schemas.AssistantWriteIntentRead(
                    intent="create_subscription",
                    target_entity_type="subscription_contract",
                    confidence=0.9,
                    data={
                        "provider": "Netflix",
                        "current_monthly_cost": 149.0,
                        "billing_frequency": "monthly",
                        "category": "streaming",
                    },
                    missing_fields=[],
                    ambiguities=[],
                ),
                "gpt-test",
                main.schemas.AIUsageRead(total_tokens=20),
            )
        return (
            "Jag behöver komplettering innan jag kan skapa ett förslag.",
            ["Vilken försäkring gäller det?", "Vad kostar den per månad?"],
            main.schemas.AssistantWriteIntentRead(
                intent="create_subscription",
                target_entity_type="subscription_contract",
                confidence=0.45,
                data={"provider": "okänd"},
                missing_fields=["category", "current_monthly_cost", "billing_frequency"],
                ambiguities=[],
            ),
            "gpt-test",
            main.schemas.AIUsageRead(total_tokens=15),
        )

    monkeypatch.setattr(main.ai_services, "generate_analysis_answer", fake_generate_analysis_answer)

    with TestClient(app) as client:
        household_id = create_local_household(client)

        normal = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "Kan du sammanfatta min ekonomi?", "conversation": []},
        )
        assert normal.status_code == 200
        assert normal.json()["write_intent"] is None

        complete = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "Lägg till Netflix som abonnemang för 149 kr per månad", "conversation": []},
        )
        assert complete.status_code == 200
        assert complete.json()["write_intent"]["intent"] == "create_subscription"
        assert complete.json()["write_intent"]["data"]["provider"] == "Netflix"

        incomplete = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "Lägg till en försäkring", "conversation": []},
        )
        assert incomplete.status_code == 200
        assert incomplete.json()["questions"]
        assert incomplete.json()["write_intent"]["missing_fields"] == [
            "category",
            "current_monthly_cost",
            "billing_frequency",
        ]

    db = database.SessionLocal()
    try:
        # Respond ska inte skriva kanonisk data utan explicit apply.
        assert db.query(models.SubscriptionContract).count() == 0
        assert db.query(models.RecurringCost).count() == 0
    finally:
        db.close()


def test_assistant_confirmation_prompt_does_not_bypass_apply(tmp_path, monkeypatch):
    app, main, database, models = load_app(tmp_path)

    def fake_generate_analysis_answer(db, household_id, prompt, conversation, settings):
        return (
            "Förslag klart.",
            [],
            main.schemas.AssistantWriteIntentRead(
                intent="create_expense",
                target_entity_type="recurring_cost",
                confidence=0.91,
                data={"category": "boende", "amount": 10000.0, "frequency": "monthly"},
                missing_fields=[],
                ambiguities=[],
            ),
            "gpt-test",
            main.schemas.AIUsageRead(total_tokens=12),
        )

    monkeypatch.setattr(main.ai_services, "generate_analysis_answer", fake_generate_analysis_answer)

    with TestClient(app) as client:
        household_id = create_local_household(client)
        first = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "Uppdatera boende till 10 000 per månad", "conversation": []},
        )
        assert first.status_code == 200
        assert first.json()["write_intent"] is not None

        confirm = client.post(
            f"/households/{household_id}/assistant/respond",
            json={"prompt": "ja skriv in korrekt i systemet nu", "conversation": []},
        )
        assert confirm.status_code == 200
        assert "Godkänn och spara" in confirm.json()["answer"]
        assert confirm.json()["write_intent"] is None

    db = database.SessionLocal()
    try:
        assert db.query(models.RecurringCost).count() == 0
    finally:
        db.close()
