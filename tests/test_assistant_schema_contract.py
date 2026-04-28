from types import SimpleNamespace

import httpx

from app import ai_services


def _fake_settings():
    return SimpleNamespace(
        openai_api_key="test-key",
        openai_analysis_model="gpt-test-analysis",
        openai_model="gpt-test",
        econ_ai_model_routing_enabled=True,
        econ_ai_default_model=None,
        econ_ai_structured_model=None,
        econ_ai_deep_analysis_model=None,
        econ_ai_fallback_model=None,
        openai_timeout_seconds=30,
        openai_base_url="https://example.invalid",
    )


def test_assistant_structured_schema_has_no_invalid_required_nodes():
    schema = ai_services._structured_schema(ai_services.AnalysisStructuredOutput, "analysis_response")["schema"]

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
            if "required" in node:
                properties = node.get("properties")
                assert isinstance(properties, dict)
                assert set(node["required"]).issubset(set(properties.keys()))
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(schema)


def test_generate_analysis_answer_maps_structured_write_intent_json(monkeypatch):
    monkeypatch.setattr(ai_services, "_compact_household_context", lambda db, household_id: {"pending_import_questions": []})
    monkeypatch.setattr(
        ai_services,
        "_call_openai_structured_with_retry",
        lambda *args, **kwargs: (
            ai_services.AnalysisStructuredOutput(
                answer_markdown="Här är ett svar.",
                questions_to_user=[],
                write_intent=ai_services.AssistantWriteIntentStructured(
                    intent="create_subscription",
                    target_entity_type="subscription_contract",
                    confidence=0.88,
                    data_json='{"provider":"Netflix","current_monthly_cost":149,"billing_frequency":"monthly","category":"streaming"}',
                    missing_fields=[],
                    ambiguities=[],
                ),
            ),
            "gpt-test-model",
            None,
        ),
    )

    answer, questions, write_intent, model_name, usage = ai_services.generate_analysis_answer(
        db=None,
        household_id=2,
        prompt="Lägg till Netflix som abonnemang för 149 kr per månad",
        conversation=[],
        settings=_fake_settings(),
    )

    assert answer == "Här är ett svar."
    assert questions == []
    assert write_intent is not None
    assert write_intent.intent == "create_subscription"
    assert write_intent.target_entity_type == "subscription_contract"
    assert write_intent.data["provider"] == "Netflix"
    assert write_intent.data["current_monthly_cost"] == 149
    assert model_name == "gpt-test-model"
    assert usage is None


def test_generate_analysis_answer_keeps_missing_fields_for_incomplete_intent(monkeypatch):
    monkeypatch.setattr(ai_services, "_compact_household_context", lambda db, household_id: {"pending_import_questions": []})
    monkeypatch.setattr(
        ai_services,
        "_call_openai_structured_with_retry",
        lambda *args, **kwargs: (
            ai_services.AnalysisStructuredOutput(
                answer_markdown="Jag behöver mer information innan jag kan skapa ett komplett förslag.",
                questions_to_user=["Vilken typ av försäkring gäller det?", "Vad kostar den per månad?"],
                write_intent=ai_services.AssistantWriteIntentStructured(
                    intent="create_subscription",
                    target_entity_type="subscription_contract",
                    confidence=0.4,
                    data_json='{"provider":"Okänd"}',
                    missing_fields=["category", "current_monthly_cost", "billing_frequency"],
                    ambiguities=[],
                ),
            ),
            "gpt-test-model",
            None,
        ),
    )

    answer, questions, write_intent, _model_name, _usage = ai_services.generate_analysis_answer(
        db=None,
        household_id=2,
        prompt="Lägg till en försäkring",
        conversation=[],
        settings=_fake_settings(),
    )

    assert "behöver mer information" in answer.lower()
    assert len(questions) == 2
    assert write_intent is not None
    assert write_intent.missing_fields == ["category", "current_monthly_cost", "billing_frequency"]


def test_generate_analysis_answer_falls_back_to_plain_text_on_schema_error(monkeypatch):
    monkeypatch.setattr(ai_services, "_compact_household_context", lambda db, household_id: {"pending_import_questions": []})

    def raise_schema_error(*args, **kwargs):
        raise ai_services.AIProviderResponseError(
            "Invalid schema for response_format 'analysis_response': strict requirement mismatch"
        )

    monkeypatch.setattr(ai_services, "_call_openai_structured_with_retry", raise_schema_error)
    monkeypatch.setattr(
        ai_services,
        "_call_openai_text",
        lambda *args, **kwargs: ("Fallback-svar i textläge.", "gpt-fallback-model", None),
    )

    answer, questions, write_intent, model_name, usage = ai_services.generate_analysis_answer(
        db=None,
        household_id=2,
        prompt="Kan du sammanfatta min ekonomi?",
        conversation=[],
        settings=_fake_settings(),
    )

    assert answer == "Fallback-svar i textläge."
    assert questions == []
    assert write_intent is None
    assert model_name == "gpt-fallback-model"
    assert usage is None


def test_select_ai_route_for_standard_prompt_uses_default_text_model():
    settings = _fake_settings()
    settings.econ_ai_default_model = "gpt-default"
    route = ai_services.select_ai_route("assistant", "Kan du sammanfatta min ekonomi?", settings, {})
    assert route.route_name == "assistant_chat"
    assert route.model == "gpt-default"
    assert route.mode == "text"
    assert route.allow_write_intent is False


def test_select_ai_route_for_complete_write_prompt_uses_structured_model():
    settings = _fake_settings()
    settings.econ_ai_structured_model = "gpt-structured"
    route = ai_services.select_ai_route(
        "assistant",
        "Lägg till Netflix som abonnemang för 149 kr per månad",
        settings,
        {},
    )
    assert route.route_name == "assistant_write_intent"
    assert route.model == "gpt-structured"
    assert route.mode == "structured"
    assert route.allow_write_intent is True


def test_select_ai_route_for_missing_write_prompt_uses_missing_info_route():
    settings = _fake_settings()
    settings.econ_ai_structured_model = "gpt-structured"
    route = ai_services.select_ai_route("assistant", "Lägg till en försäkring", settings, {})
    assert route.route_name == "assistant_missing_info"
    assert route.model == "gpt-structured"
    assert route.structured_required is True


def test_select_ai_route_for_deep_analysis_prompt_uses_deep_model():
    settings = _fake_settings()
    settings.econ_ai_deep_analysis_model = "gpt-deep"
    route = ai_services.select_ai_route(
        "assistant",
        "Gör en djup analys av hela hushållets ekonomi och hitta motsägelser",
        settings,
        {},
    )
    assert route.route_name == "deep_analysis"
    assert route.model == "gpt-deep"
    assert route.allow_write_intent is False


def test_generate_analysis_answer_uses_fallback_model_when_structured_schema_fails(monkeypatch):
    settings = _fake_settings()
    settings.econ_ai_structured_model = "gpt-structured"
    settings.econ_ai_fallback_model = "gpt-fallback"
    monkeypatch.setattr(ai_services, "_compact_household_context", lambda db, household_id: {"pending_import_questions": []})

    def raise_schema_error(*args, **kwargs):
        raise ai_services.AIProviderResponseError(
            "Invalid schema for response_format 'analysis_response': strict requirement mismatch"
        )

    captured = {}

    def fake_call_openai_text(_settings, *, model, instructions, payload, max_output_tokens):
        captured["model"] = model
        return "Fallback text", "gpt-fallback-runtime", None

    monkeypatch.setattr(ai_services, "_call_openai_structured_with_retry", raise_schema_error)
    monkeypatch.setattr(ai_services, "_call_openai_text", fake_call_openai_text)

    answer, questions, write_intent, _model_name, _usage = ai_services.generate_analysis_answer(
        db=None,
        household_id=2,
        prompt="Lägg till en försäkring",
        conversation=[],
        settings=settings,
    )

    assert answer == "Fallback text"
    assert questions == []
    assert write_intent is None
    assert captured["model"] == "gpt-fallback"


def test_call_openai_structured_maps_request_error_to_provider_error(monkeypatch):
    settings = _fake_settings()

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            raise httpx.RequestError("network down")

    monkeypatch.setattr(ai_services.httpx, "Client", FailingClient)

    try:
        ai_services._call_openai_structured(
            settings,
            model="gpt-test",
            instructions="test",
            payload={"x": 1},
            response_model=ai_services.AnalysisStructuredOutput,
            schema_name="analysis_response",
            max_output_tokens=100,
        )
    except ai_services.AIProviderResponseError as exc:
        assert "nätverksfel" in str(exc).lower()
    else:
        raise AssertionError("Expected AIProviderResponseError")


def test_call_openai_text_maps_request_error_to_provider_error(monkeypatch):
    settings = _fake_settings()

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            raise httpx.RequestError("network down")

    monkeypatch.setattr(ai_services.httpx, "Client", FailingClient)

    try:
        ai_services._call_openai_text(
            settings,
            model="gpt-test",
            instructions="test",
            payload={"x": 1},
            max_output_tokens=100,
        )
    except ai_services.AIProviderResponseError as exc:
        assert "nätverksfel" in str(exc).lower()
    else:
        raise AssertionError("Expected AIProviderResponseError")
