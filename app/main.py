"""
FastAPI application entry point for the household economics backend.

This module wires together the database, models, schemas and API routes to
expose a RESTful interface for manipulating the core domain objects defined
in ``models.py``. Each entity has endpoints for listing, creating,
retrieving, updating and deleting records. The API is intentionally
minimalistic and CRUD-focused in order to provide a solid foundation for
future business logic, calculations and integrations. More complex
operations (e.g. scenario simulation or optimization) should be added in
dedicated routes or services without polluting basic CRUD handlers.

Usage::

    uvicorn app.main:app --reload

The ``init_db`` function will ensure that database tables are created on
application startup. The database connection URL can be configured via
the ``DATABASE_URL`` environment variable. When deploying behind a
reverse proxy or within a Tailscale network, ensure that appropriate
authentication and transport security is applied at the proxy layer.
"""

import hashlib
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from typing import Any, List, Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Body, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import ai_services, calculations, database, import_services, models, pdf_export, schemas, auth
from .analysis import schemas as analysis_schemas
from .analysis.cycle_engine import compute_cycle_status
from .analysis.pipeline import build_analysis_output
from .ingest_content import extract_text_from_upload, normalize_ingest_text
from .settings import get_settings

settings = get_settings()
app = FastAPI(title="Household Economics Backend", version="0.1.0")
STATIC_ROOT = Path(__file__).resolve().parent / "static"
UPLOAD_ROOT = Path(settings.upload_dir).resolve()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)


from fastapi import Request

API_ROUTE_PREFIXES = (
    "/households",
    "/persons",
    "/income_sources",
    "/loans",
    "/recurring_costs",
    "/subscription_contracts",
    "/insurance_policies",
    "/vehicles",
    "/financial_assets",
    "/housing_scenarios",
    "/documents",
    "/extraction_drafts",
    "/optimization_opportunities",
    "/scenarios",
    "/scenario_results",
    "/report_snapshots",
    "/system",
)


def _is_public_frontend_request(request: Request) -> bool:
    path = request.url.path
    if path.startswith("/assets") or path.startswith("/static") or path.startswith("/auth"):
        return True
    if path in {"/", "/healthz", "/docs", "/openapi.json", "/favicon.ico"}:
        return True
    if request.method not in {"GET", "HEAD"}:
        return False
    return not any(path == prefix or path.startswith(f"{prefix}/") for prefix in API_ROUTE_PREFIXES)


def _should_disable_cache(path: str) -> bool:
    if path in {"/healthz", "/docs", "/openapi.json"} or path.startswith("/auth"):
        return False
    if path == "/favicon.ico":
        return True
    if path.startswith("/assets") or path.startswith("/static"):
        return True
    return not any(path == prefix or path.startswith(f"{prefix}/") for prefix in API_ROUTE_PREFIXES)

# Basic Auth protection wrapper for endpoints
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if _is_public_frontend_request(request):
        response = await call_next(request)
        if _should_disable_cache(request.url.path):
            response.headers["Cache-Control"] = "no-store"
        return response

    import os
    if os.environ.get("BYPASS_AUTH", "false").lower() == "true":
        request.state.user_id = 999
        response = await call_next(request)
        if _should_disable_cache(request.url.path):
            response.headers["Cache-Control"] = "no-store"
        return response

    # Check for Bearer token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # Check cookies too for SPA convenience
        token = request.cookies.get("he_session")
        if not token:
            return Response("Unauthorized. Please log in.", status_code=401)
    else:
        token = auth_header.split(" ")[1]

    # Validate token (in our MVP, token is just a random hex string stored in AuthSession)
    db = database.SessionLocal()
    session = db.query(models.AuthSession).filter(models.AuthSession.session_token == token).first()
    if not session or session.expires_at < datetime.utcnow():
        db.close()
        return Response("Session expired or invalid", status_code=401)

    # Extend session slightly on activity
    try:
        request.state.user_id = session.user_id
        # Optionally extend logic here
    finally:
        db.close()

    response = await call_next(request)
    if _should_disable_cache(request.url.path):
        response.headers["Cache-Control"] = "no-store"
    return response

# Dependency that provides a database session per request. The session
# is cleaned up automatically once the request is finished. If you
# require transactional behaviour across multiple requests you should
# implement that at a higher abstraction level.
def get_db() -> Session:
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    """Initialise the database on application startup."""
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    database.init_db()


def get_object_or_404(db: Session, model, obj_id: int):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"{model.__name__} with id {obj_id} not found")
    return obj


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/system/validation_markdown", include_in_schema=False)
def system_validation_markdown():
    return FileResponse(Path(__file__).resolve().parents[1] / "docs" / "SYSTEM_VALIDATION.md")

if STATIC_ROOT.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_ROOT), name="assets")
    # Also mount static for users who already cached the /static paths
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


@app.get("/")
def home():
    return FileResponse(STATIC_ROOT / "index.html")


def _request_household_id(request: Request, db: Session) -> int | None:
    user_id = getattr(request.state, "user_id", None)
    if user_id in {None, 999}:
        return None
    user = db.get(models.AppUser, user_id)
    return user.household_id if user is not None else None


def ensure_household_exists(db: Session, household_id: int, request: Request | None = None):
    household = get_object_or_404(db, models.Household, household_id)
    if request is not None:
        user_id = getattr(request.state, "user_id", None)
        if user_id not in {None, 999}:
            user = db.get(models.AppUser, user_id)
            if user is None or user.household_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Inloggad användare saknar kopplat hushåll.",
                )
            if user.household_id != household_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Hushållet tillhör inte den inloggade användaren.",
                )
    return household


DOCUMENT_WORKFLOW_STATUS = {
    "uploaded",
    "interpreting",
    "interpreted",
    "pending_review",
    "applied",
    "failed",
    "rejected",
    "manual_link_required",
}

DOCUMENT_STATUS_LABELS = {
    "uploaded": "Uppladdad",
    "interpreting": "Tolkas",
    "interpreted": "Tolkad",
    "pending_review": "Väntar på granskning",
    "manual_link_required": "Kräver manuell koppling",
    "approved": "Godkänd",
    "applied": "Applicerad",
    "rejected": "Avvisad",
    "deferred": "Uppskjuten",
    "failed": "Misslyckad",
}

WORKFLOW_STEP_ORDER = ("uploaded", "interpreting", "interpreted", "pending_review", "applied", "failed")

LOAN_REVIEW_FIELD_LABELS = {
    "lender": "Långivare",
    "interest_rate": "Ränta",
    "nominal_rate": "Ränta",
    "debt_before_amortization": "Skuld före amortering",
    "current_balance": "Skuld före amortering",
    "payment_amount": "Belopp att betala",
    "required_monthly_payment": "Belopp att betala",
    "payment_due_date": "Förfallodatum",
    "due_date": "Förfallodatum",
    "object_vehicle": "Objekt / bil",
    "purpose": "Objekt / bil",
    "contract_number": "Kontraktsnummer",
    "amortization": "Amortering",
    "amortization_amount_monthly": "Amortering",
    "interest_cost": "Räntekostnad",
    "interest_cost_amount": "Räntekostnad",
    "fees": "Avgifter",
    "fee_amount": "Avgifter",
}


def _status_label_sv(status: str | None) -> str:
    return DOCUMENT_STATUS_LABELS.get(status or "", status or "Okänd")


def _normalize_entity_text(value: Any) -> str:
    text = str(value or "").lower().strip()
    for ch in ".,;:/\\()[]{}<>|\"'":
        text = text.replace(ch, " ")
    return " ".join(text.split())


def _vehicle_label_from_payload(payload: dict[str, Any]) -> str | None:
    raw = payload.get("object_vehicle") or payload.get("purpose") or payload.get("label")
    if not raw:
        return None
    return str(raw).strip() or None


def _split_vehicle_label(label: str | None) -> tuple[str | None, str | None]:
    cleaned = " ".join(str(label or "").split()).strip()
    if not cleaned:
        return None, None
    parts = cleaned.split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def _vehicle_display_label(vehicle: models.Vehicle | None) -> str:
    if vehicle is None:
        return "Fordon"
    parts = [part for part in [vehicle.make, vehicle.model] if part]
    if parts:
        return " ".join(parts)
    return f"Fordon #{vehicle.id}"


def _loan_display_label(loan: models.Loan | None) -> str:
    if loan is None:
        return "Lån"
    parts = [part for part in [loan.lender, loan.purpose] if part]
    if parts:
        return " · ".join(parts)
    return f"Lån #{loan.id}"


def _draft_review_payload(draft: models.ExtractionDraft) -> dict[str, Any]:
    review_payload = dict(draft.review_json or {})
    canonical_payload = dict(draft.proposed_json or {})
    payload = review_payload or canonical_payload
    if draft.target_entity_type == "loan":
        payload = _enrich_loan_payload(dict(canonical_payload), review_payload)
    return payload


def _draft_requires_manual_link(draft: models.ExtractionDraft) -> bool:
    summary = dict(draft.apply_summary_json or {})
    if summary.get("manual_actions_required"):
        return True
    if summary.get("status") == "manual_review":
        return True
    return False


def _build_status_steps(workflow_status: str, drafts: list[models.ExtractionDraft]) -> list[schemas.DocumentWorkflowStepRead]:
    active_index = WORKFLOW_STEP_ORDER.index(workflow_status) if workflow_status in WORKFLOW_STEP_ORDER else 0
    steps = []
    for index, key in enumerate(WORKFLOW_STEP_ORDER):
        steps.append(
            schemas.DocumentWorkflowStepRead(
                key=key,
                label_sv=_status_label_sv(key),
                active=index == active_index,
                completed=index < active_index,
            )
        )
    if any(_draft_requires_manual_link(draft) for draft in drafts):
        steps.append(
            schemas.DocumentWorkflowStepRead(
                key="manual_link_required",
                label_sv="Kräver manuell koppling",
                active=False,
                completed=False,
            )
        )
    if any(draft.status == "rejected" for draft in drafts):
        steps.append(
            schemas.DocumentWorkflowStepRead(
                key="rejected",
                label_sv="Avvisad",
                active=False,
                completed=False,
            )
        )
    return steps


def _status_label_for_workflow(document: models.Document, drafts: list[models.ExtractionDraft]) -> str:
    if document.processing_error or any(d.status == "apply_failed" for d in drafts):
        return "Misslyckad"
    if any(d.status == "rejected" for d in drafts) and not any(d.status in {"pending_review", "approved"} for d in drafts):
        return "Avvisad"
    if any(_draft_requires_manual_link(draft) for draft in drafts):
        return "Kräver manuell koppling"
    return _status_label_sv(document.extraction_status)


def _status_for_uploaded_document(extracted_text: str | None, extraction_mode: str) -> tuple[str, str | None]:
    if extracted_text and extracted_text.strip():
        return "interpreted", None

    error_map = {
        "unsupported_binary": "Filtypen stöds inte.",
        "pdf_unreadable": "PDF-filen är skadad eller lösenordsskyddad.",
        "ocr_image_unreadable": "Bilden kunde inte läsas av OCR-motorn.",
        "ocr_failed": "OCR-analysen misslyckades oväntat.",
        "ocr_no_text": "Hittade ingen text i bilden (för suddig eller tom?).",
        "spreadsheet_unreadable": "Kalkylbladet kunde inte läsas (skadad eller skyddad fil).",
        "spreadsheet_missing_dependency": "Systemet saknar bibliotek för att läsa denna filtyp.",
        "excel_legacy_unsupported": "Äldre Excel-format stöds inte (spara som .xlsx).", # Keeping for safety though removed from ingest
    }

    if extraction_mode in error_map:
        return "failed", f"Det gick inte att tolka dokumentet: {error_map[extraction_mode]} ({extraction_mode})"

    return "uploaded", None


def _public_ai_error_detail(exc: Exception, *, surface: str) -> str:
    detail = str(exc)
    lowered = detail.lower()

    if any(token in lowered for token in ("ogiltig json", "utan läsbar text", "responses api", "json för", "schema")):
        if surface == "assistant":
            return "AI-assistenten kunde inte validera svaret just nu. Försök igen om en stund."
        return "AI-tolkningen kunde inte slutföras för underlaget. Försök igen eller korrigera texten manuellt."

    if "openai-anropet misslyckades" in lowered:
        if surface == "assistant":
            return "AI-assistenten kunde inte svara just nu. Försök igen om en stund."
        return "AI-tolkningen kunde inte slutföras just nu. Försök igen eller använd råtextfältet."

    return detail


def _draft_status_detail(drafts: list[models.ExtractionDraft]) -> str | None:
    if any(d.status == "apply_failed" for d in drafts):
        failed = next((d for d in drafts if d.status == "apply_failed" and d.review_error), None)
        return failed.review_error if failed else "Ett utkast kunde inte appliceras."
    if drafts and all(d.status == "rejected" for d in drafts):
        return "Alla utkast avvisades."
    if any(d.status == "pending_review" for d in drafts):
        count = sum(1 for d in drafts if d.status == "pending_review")
        if any(_draft_requires_manual_link(d) for d in drafts):
            return f"{count} utkast väntar på granskning och kräver manuell koppling."
        return f"{count} utkast väntar på granskning."
    if any(d.status == "deferred" for d in drafts):
        count = sum(1 for d in drafts if d.status == "deferred")
        return f"{count} utkast är uppskjutna."
    if any(d.status == "approved" and d.canonical_target_entity_id for d in drafts):
        count = sum(1 for d in drafts if d.status == "approved" and d.canonical_target_entity_id)
        manual = sum(1 for d in drafts if _draft_requires_manual_link(d))
        if manual:
            return f"{count} utkast har applicerats till kanonisk data. {manual} kräver manuell koppling."
        return f"{count} utkast har applicerats till kanonisk data."
    return None


def _derive_document_workflow_status(document: models.Document, drafts: list[models.ExtractionDraft]) -> tuple[str, str | None]:
    if document.processing_error:
        return "failed", document.processing_error
    if any(d.status == "apply_failed" for d in drafts):
        return "failed", _draft_status_detail(drafts)
    if any(_draft_requires_manual_link(d) for d in drafts):
        return "manual_link_required", _draft_status_detail(drafts)
    if any(d.status == "pending_review" for d in drafts):
        return "pending_review", _draft_status_detail(drafts)
    if drafts and all(d.status == "rejected" for d in drafts):
        return "rejected", _draft_status_detail(drafts)
    if any(d.status == "deferred" for d in drafts):
        return "deferred", _draft_status_detail(drafts)
    if any(d.status == "approved" and d.canonical_target_entity_id for d in drafts):
        return "applied", _draft_status_detail(drafts)
    if document.extracted_text:
        return "interpreted", "Dokumentet har tolkats men inte blivit reviewutkast ännu."
    return "uploaded", "Dokumentet är uppladdat men ännu inte tolkat."


def _update_document_workflow_status(document: models.Document) -> tuple[str, str | None]:
    status_value, detail = _derive_document_workflow_status(document, list(document.extraction_drafts or []))
    document.extraction_status = status_value
    if status_value != "failed":
        document.processing_error = None
    return status_value, detail


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _stringify_review_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        return str(round(value, 2))
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _canonical_target_label(entity_type: str, entity: Any) -> str:
    if entity_type == "loan":
        lender = getattr(entity, "lender", None) or "Lån"
        purpose = getattr(entity, "purpose", None)
        return f"{lender} · {purpose}" if purpose else lender
    if entity_type == "vehicle":
        make = getattr(entity, "make", None)
        model = getattr(entity, "model", None)
        if make or model:
            return " ".join(part for part in [make, model] if part)
        return f"Fordon #{entity.id}"
    return getattr(entity, "name", None) or getattr(entity, "title", None) or f"{entity_type} #{entity.id}"


def _load_alias_map(db: Session, household_id: int) -> dict[str, str]:
    aliases = db.query(models.MerchantAlias).filter_by(household_id=household_id).all()
    return {(_normalize_entity_text(alias.alias)): alias.canonical_name for alias in aliases if alias.alias}


def _normalize_with_aliases(text: str | None, alias_map: dict[str, str]) -> str:
    normalized = _normalize_entity_text(text)
    if not normalized:
        return ""
    for alias, canonical in alias_map.items():
        if alias and alias in normalized:
            normalized = normalized.replace(alias, _normalize_entity_text(canonical))
    return " ".join(normalized.split())


def _score_text_match(candidate_text: str | None, source_text: str | None) -> float:
    candidate = _normalize_entity_text(candidate_text)
    source = _normalize_entity_text(source_text)
    if not candidate or not source:
        return 0.0
    if candidate == source:
        return 1.0
    if candidate in source or source in candidate:
        return 0.92
    candidate_tokens = set(candidate.split())
    source_tokens = set(source.split())
    if not candidate_tokens or not source_tokens:
        return 0.0
    overlap = len(candidate_tokens & source_tokens) / len(candidate_tokens | source_tokens)
    return round(overlap, 2)


def _vehicle_match_score(vehicle: models.Vehicle, label: str | None, alias_map: dict[str, str]) -> float:
    vehicle_text = " ".join(part for part in [vehicle.make, vehicle.model] if part)
    if not vehicle_text:
        return 0.0
    normalized_vehicle = _normalize_with_aliases(vehicle_text, alias_map)
    normalized_label = _normalize_with_aliases(label, alias_map)
    return max(_score_text_match(normalized_vehicle, normalized_label), _score_text_match(vehicle_text, label))


def _loan_match_score(loan: models.Loan, lender: str | None, purpose: str | None, amount: float | None, alias_map: dict[str, str]) -> float:
    lender_score = _score_text_match(_normalize_with_aliases(loan.lender, alias_map), lender)
    purpose_score = _score_text_match(loan.purpose, purpose)
    score = max(lender_score, purpose_score)
    if amount is not None and loan.required_monthly_payment is not None:
        diff = abs(float(loan.required_monthly_payment) - float(amount))
        if diff == 0:
            score = max(score, 0.9)
        elif diff <= max(150.0, float(amount) * 0.12):
            score = max(score, 0.82)
    return round(score, 2)


def _build_document_entity_resolutions(
    db: Session,
    document: models.Document,
    drafts: list[models.ExtractionDraft],
) -> list[schemas.DocumentEntityResolutionRead]:
    alias_map = _load_alias_map(db, document.household_id)
    household_loans = db.query(models.Loan).filter_by(household_id=document.household_id).all()
    household_vehicles = db.query(models.Vehicle).filter_by(household_id=document.household_id).all()
    resolutions: list[schemas.DocumentEntityResolutionRead] = []

    for draft in drafts:
        payload = _draft_review_payload(draft)
        if draft.target_entity_type != "loan":
            continue

        lender = payload.get("lender")
        purpose = payload.get("purpose") or payload.get("object_vehicle")
        monthly_payment = payload.get("required_monthly_payment") or payload.get("payment_amount")
        vehicle_label = _vehicle_label_from_payload(payload)

        loan_candidates = sorted(
            household_loans,
            key=lambda loan: _loan_match_score(loan, lender, purpose, monthly_payment, alias_map),
            reverse=True,
        )
        loan_candidate_reads = []
        for loan in loan_candidates[:3]:
            confidence = _loan_match_score(loan, lender, purpose, monthly_payment, alias_map)
            if confidence <= 0:
                continue
            loan_candidate_reads.append(
                schemas.DocumentEntityResolutionCandidateRead(
                    entity_type="loan",
                    entity_id=loan.id,
                    label=_loan_display_label(loan),
                    confidence=confidence,
                    reason="Liknar leverantör, syfte eller månadskostnad i dokumentet.",
                    recommended_action="link_existing" if confidence >= 0.8 else "manual_review",
                )
            )
        if (lender or purpose or monthly_payment is not None) and not any(
            candidate.entity_id is None and candidate.recommended_action == "create_new" for candidate in loan_candidate_reads
        ):
            loan_candidate_reads.append(
                schemas.DocumentEntityResolutionCandidateRead(
                    entity_type="loan",
                    entity_id=None,
                    label=lender or purpose or "Nytt lån",
                    confidence=0.86 if (lender or purpose) else 0.72,
                    reason="Skapa ett nytt lån om ingen befintlig post ska uppdateras.",
                    recommended_action="create_new",
                )
            )

        vehicle_candidates = sorted(
            household_vehicles,
            key=lambda vehicle: _vehicle_match_score(vehicle, vehicle_label or purpose, alias_map),
            reverse=True,
        )
        vehicle_candidate_reads = []
        for vehicle in vehicle_candidates[:3]:
            confidence = _vehicle_match_score(vehicle, vehicle_label or purpose, alias_map)
            if confidence <= 0:
                continue
            vehicle_candidate_reads.append(
                schemas.DocumentEntityResolutionCandidateRead(
                    entity_type="vehicle",
                    entity_id=vehicle.id,
                    label=_vehicle_display_label(vehicle),
                    confidence=confidence,
                    reason="Liknar fordonet som nämns i dokumentet.",
                    recommended_action="link_existing" if confidence >= 0.75 else "manual_review",
                )
            )
        if (vehicle_label or purpose) and not any(
            candidate.entity_id is None and candidate.recommended_action == "create_new" for candidate in vehicle_candidate_reads
        ):
            vehicle_candidate_reads.append(
                schemas.DocumentEntityResolutionCandidateRead(
                    entity_type="vehicle",
                    entity_id=None,
                    label=vehicle_label or purpose or "Nytt fordon",
                    confidence=0.86 if vehicle_label else 0.72,
                    reason="Skapa ett nytt fordon om ingen befintlig post ska kopplas.",
                    recommended_action="create_new",
                )
            )

        best_loan = loan_candidate_reads[0] if loan_candidate_reads else None
        best_vehicle = vehicle_candidate_reads[0] if vehicle_candidate_reads else None
        if best_loan and best_loan.confidence is not None and best_loan.confidence >= 0.85:
            recommended_action = "link_existing"
            reason = "Det finns redan ett tydligt matchande lån."
        elif best_vehicle and best_vehicle.confidence is not None and best_vehicle.confidence >= 0.8:
            recommended_action = "create_new"
            reason = "Dokumentet pekar tydligt på ett fordon, men lånet verkar sakna stabil träff."
        else:
            recommended_action = "manual_review" if loan_candidate_reads or vehicle_candidate_reads else "create_new"
            reason = "Systemet har för få säkra signaler för att koppla automatiskt."

        resolutions.append(
            schemas.DocumentEntityResolutionRead(
                draft_id=draft.id,
                primary_entity_type="loan",
                recommended_action=recommended_action,
                confidence=best_loan.confidence if best_loan else (best_vehicle.confidence if best_vehicle else None),
                reason=reason,
                loan_candidates=loan_candidate_reads,
                vehicle_candidates=vehicle_candidate_reads,
            )
        )

    return resolutions


def _build_document_key_fields(document: models.Document, drafts: list[models.ExtractionDraft], db: Session) -> list[schemas.DocumentKeyFieldRead]:
    seen: set[tuple[str, str, str]] = set()
    key_fields: list[schemas.DocumentKeyFieldRead] = []

    def add_field(key: str, label: str, value: Any, source: str) -> None:
        rendered = _stringify_review_value(value)
        if not rendered:
            return
        token = (key, rendered, source)
        if token in seen:
            return
        seen.add(token)
        key_fields.append(
            schemas.DocumentKeyFieldRead(key=key, label=label, value=rendered, source=source)
        )

    add_field("file_name", "Dokument", document.file_name, "document")
    add_field("issuer", "Avsändare", document.issuer, "document")
    add_field("total_amount", "Belopp", document.total_amount, "document")
    add_field("issue_date", "Dokumentdatum", document.issue_date, "document")

    for draft in drafts:
        review_payload = dict(draft.review_json or {})
        canonical_payload = dict(draft.proposed_json or {})
        source = "draft_review" if review_payload else "draft_canonical"
        payload = review_payload or canonical_payload
        if draft.target_entity_type == "loan":
            for key, label in LOAN_REVIEW_FIELD_LABELS.items():
                add_field(key, label, payload.get(key), source)
        else:
            add_field("title", "Titel", payload.get("title") or payload.get("provider") or payload.get("vendor"), source)
            add_field("amount", "Belopp", payload.get("amount") or payload.get("current_monthly_cost"), source)

        if draft.canonical_target_entity_type and draft.canonical_target_entity_id:
            model_map = {"loan": models.Loan, "vehicle": models.Vehicle}
            model_class = model_map.get(draft.canonical_target_entity_type)
            if model_class is not None:
                entity = db.get(model_class, draft.canonical_target_entity_id)
                if entity is not None and draft.canonical_target_entity_type == "loan":
                    add_field("canonical_lender", "Kopplat lån", _canonical_target_label("loan", entity), "canonical_record")
                    add_field("canonical_current_balance", "Aktuell skuld", getattr(entity, "current_balance", None), "canonical_record")
                    add_field("canonical_required_monthly_payment", "Månad att betala", getattr(entity, "required_monthly_payment", None), "canonical_record")
                if entity is not None and draft.canonical_target_entity_type == "vehicle":
                    add_field("canonical_vehicle", "Kopplat fordon", _canonical_target_label("vehicle", entity), "canonical_record")
                    owner = db.get(models.Person, getattr(entity, "owner_person_id", None)) if getattr(entity, "owner_person_id", None) else None
                    add_field("canonical_vehicle_owner", "Fordonsägare", getattr(owner, "name", None), "canonical_record")
        if draft.apply_summary_json:
            summary = dict(draft.apply_summary_json)
            for mutation in summary.get("mutations", []):
                entity_type = mutation.get("entity_type")
                label = mutation.get("label")
                summary_text = mutation.get("summary_sv")
                if entity_type and label:
                    add_field(f"apply_{entity_type}", f"Applicerat {entity_type}", f"{label} · {summary_text}", "canonical_record")
    return key_fields


def _build_document_workflow_read(db: Session, document: models.Document) -> schemas.DocumentWorkflowRead:
    drafts = (
        db.query(models.ExtractionDraft)
        .filter_by(document_id=document.id)
        .order_by(models.ExtractionDraft.created_at.desc())
        .all()
    )
    status_value, detail = _derive_document_workflow_status(document, drafts)
    entity_resolutions = _build_document_entity_resolutions(db, document, drafts)
    if status_value == "pending_review" and any(
        resolution.recommended_action == "manual_review" for resolution in entity_resolutions
    ):
        status_value = "manual_link_required"
        detail = "Dokumentet väntar på ditt val för att kopplas till rätt objekt."
    document.extraction_status = status_value
    canonical_links: list[schemas.CanonicalLinkRead] = []
    latest_apply_summary: dict[str, Any] | None = None
    seen_links: set[tuple[str, int]] = set()
    for draft in drafts:
        if not draft.canonical_target_entity_type or not draft.canonical_target_entity_id:
            if draft.apply_summary_json and latest_apply_summary is None:
                latest_apply_summary = dict(draft.apply_summary_json)
            continue
        model_map = {"loan": models.Loan, "vehicle": models.Vehicle}
        model_class = model_map.get(draft.canonical_target_entity_type)
        entity = db.get(model_class, draft.canonical_target_entity_id) if model_class is not None else None
        target_label = _canonical_target_label(draft.canonical_target_entity_type, entity) if entity is not None else f"{draft.canonical_target_entity_type} #{draft.canonical_target_entity_id}"
        canonical_links.append(
            schemas.CanonicalLinkRead(
                draft_id=draft.id,
                target_entity_type=draft.canonical_target_entity_type,
                target_entity_id=draft.canonical_target_entity_id,
                target_label=target_label,
                applied_at=draft.applied_at,
            )
        )
        seen_links.add((draft.canonical_target_entity_type, draft.canonical_target_entity_id))
        if draft.canonical_target_entity_type == "loan":
            linked_vehicle = (
                db.query(models.Vehicle)
                .filter_by(household_id=document.household_id, loan_id=draft.canonical_target_entity_id)
                .order_by(models.Vehicle.id.asc())
                .first()
            )
            if linked_vehicle is not None and ("vehicle", linked_vehicle.id) not in seen_links:
                canonical_links.append(
                    schemas.CanonicalLinkRead(
                        draft_id=draft.id,
                        target_entity_type="vehicle",
                        target_entity_id=linked_vehicle.id,
                        target_label=_canonical_target_label("vehicle", linked_vehicle),
                        applied_at=draft.applied_at,
                    )
                )
                seen_links.add(("vehicle", linked_vehicle.id))
        if draft.apply_summary_json and latest_apply_summary is None:
            latest_apply_summary = dict(draft.apply_summary_json)

    if latest_apply_summary is not None:
        latest_apply_summary.setdefault("document_id", document.id)
        latest_apply_summary.setdefault(
            "applied_at",
            drafts[0].applied_at if drafts and drafts[0].applied_at else document.uploaded_at,
        )

    recommended_actions = ["Granska extraherade nyckelfält"]
    if entity_resolutions:
        if any(resolution.loan_candidates for resolution in entity_resolutions):
            recommended_actions.append("Bekräfta vilket lån som ska uppdateras eller om ett nytt lån ska skapas")
        if any(_vehicle_label_from_payload(_draft_review_payload(draft)) for draft in drafts if draft.target_entity_type == "loan"):
            recommended_actions.append("Bekräfta om fordonet ska kopplas till befintligt eller nytt fordon")
    else:
        recommended_actions.append("Ladda upp eller tolka dokumentet för att se förslag")

    return schemas.DocumentWorkflowRead(
        document=document,
        workflow_status=status_value,
        status_detail=detail,
        status_label_sv=_status_label_for_workflow(document, drafts),
        status_steps=_build_status_steps(status_value, drafts),
        drafts=drafts,
        key_fields=_build_document_key_fields(document, drafts, db),
        canonical_links=canonical_links,
        entity_resolutions=entity_resolutions,
        apply_summary=latest_apply_summary,
        recommended_actions=recommended_actions,
        requires_manual_link=status_value == "manual_link_required" or any(_draft_requires_manual_link(draft) for draft in drafts),
    )


def _append_loan_note(existing_note: str | None, review_payload: dict[str, Any]) -> str | None:
    extras = []
    if review_payload.get("contract_number"):
        extras.append(f"Kontraktsnummer: {review_payload['contract_number']}")
    if review_payload.get("interest_cost") is not None or review_payload.get("interest_cost_amount") is not None:
        extras.append(f"Räntekostnad: {review_payload.get('interest_cost') or review_payload.get('interest_cost_amount')}")
    if review_payload.get("fees") is not None or review_payload.get("fee_amount") is not None:
        extras.append(f"Avgifter: {review_payload.get('fees') or review_payload.get('fee_amount')}")
    if review_payload.get("payment_due_date"):
        extras.append(f"Förfallodatum: {review_payload['payment_due_date']}")
    note_parts = [part for part in [existing_note] + extras if part]
    return "\n".join(note_parts) if note_parts else None


def _enrich_loan_payload(canonical_payload: dict[str, Any], review_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(canonical_payload)
    if "household_id" not in payload and review_payload.get("household_id") is not None:
        payload["household_id"] = review_payload["household_id"]
    if payload.get("current_balance") is None and review_payload.get("debt_before_amortization") is not None:
        payload["current_balance"] = review_payload["debt_before_amortization"]
    if payload.get("required_monthly_payment") is None and review_payload.get("payment_amount") is not None:
        payload["required_monthly_payment"] = review_payload["payment_amount"]
    if payload.get("nominal_rate") is None and review_payload.get("interest_rate") is not None:
        payload["nominal_rate"] = review_payload["interest_rate"]
    if payload.get("amortization_amount_monthly") is None and review_payload.get("amortization") is not None:
        payload["amortization_amount_monthly"] = review_payload["amortization"]
    if payload.get("purpose") in {None, ""} and review_payload.get("object_vehicle"):
        payload["purpose"] = review_payload["object_vehicle"]
    due_date_value = review_payload.get("payment_due_date") or review_payload.get("due_date")
    parsed_due_date = _parse_iso_date(due_date_value)
    if payload.get("due_day") is None and parsed_due_date is not None:
        payload["due_day"] = parsed_due_date.day
    payload["note"] = _append_loan_note(payload.get("note"), review_payload)
    return payload


def _pick_draft_action(
    request_body: schemas.DocumentApplyRequest,
    draft: models.ExtractionDraft,
    resolution: schemas.DocumentEntityResolutionRead | None,
) -> schemas.DocumentDraftApplySelection | None:
    explicit = next((item for item in request_body.draft_actions if item.draft_id == draft.id), None)
    if explicit is not None:
        return explicit
    if resolution is not None and resolution.recommended_action == "manual_review":
        return None
    if (
        resolution is not None
        and resolution.recommended_action == "link_existing"
        and resolution.loan_candidates
        and resolution.loan_candidates[0].entity_id is not None
    ):
        return schemas.DocumentDraftApplySelection(
            draft_id=draft.id,
            action="link_existing",
            target_entity_id=resolution.loan_candidates[0].entity_id,
            proposed_json=request_body.proposed_json,
        )
    return schemas.DocumentDraftApplySelection(
        draft_id=draft.id,
        action=request_body.action,
        target_entity_id=request_body.target_entity_id,
        proposed_json=request_body.proposed_json,
    )


def _pick_related_action(
    request_body: schemas.DocumentApplyRequest,
    draft: models.ExtractionDraft,
    resolution: schemas.DocumentEntityResolutionRead | None,
    payload: dict[str, Any],
) -> schemas.RelatedEntityApplySelection | None:
    explicit = next((item for item in request_body.related_actions if item.source_draft_id == draft.id), None)
    if explicit is not None:
        return explicit
    vehicle_label = _vehicle_label_from_payload(payload)
    if not vehicle_label:
        return None
    if resolution is None:
        return schemas.RelatedEntityApplySelection(
            source_draft_id=draft.id,
            entity_type="vehicle",
            action="create_new",
        )
    best_vehicle = resolution.vehicle_candidates[0] if resolution.vehicle_candidates else None
    if best_vehicle and best_vehicle.recommended_action == "link_existing" and best_vehicle.entity_id is not None:
        return schemas.RelatedEntityApplySelection(
            source_draft_id=draft.id,
            entity_type="vehicle",
            action="link_existing",
            target_entity_id=best_vehicle.entity_id,
        )
    create_new_candidate = next(
        (
            candidate
            for candidate in (resolution.vehicle_candidates if resolution else [])
            if candidate.recommended_action == "create_new" and candidate.entity_id is None
        ),
        None,
    )
    if create_new_candidate is not None:
        return schemas.RelatedEntityApplySelection(
            source_draft_id=draft.id,
            entity_type="vehicle",
            action="create_new",
        )
    if resolution.recommended_action == "manual_review" and resolution.vehicle_candidates:
        return None
    if request_body.related_actions:
        return None
    return schemas.RelatedEntityApplySelection(
        source_draft_id=draft.id,
        entity_type="vehicle",
        action="create_new",
    )


def _apply_non_loan_draft(
    db: Session,
    *,
    draft: models.ExtractionDraft,
    document: models.Document,
    selection: schemas.DocumentDraftApplySelection,
) -> tuple[Any, str]:
    (schema_class, model_class), normalized = draft_target_config(draft.target_entity_type)
    proposed = dict(draft.proposed_json or {})
    if selection.proposed_json:
        proposed.update(selection.proposed_json)
    if "household_id" in getattr(schema_class, "__fields__", {}) and "household_id" not in proposed:
        proposed["household_id"] = draft.household_id
    if selection.action == "link_existing":
        raise HTTPException(status_code=400, detail="Befintlig koppling stöds bara för lån i dokumentpaket-flödet.")
    payload = schema_class(**proposed)
    entity = model_class(**payload.dict())
    db.add(entity)
    db.flush()
    if normalized == "document":
        document.processing_error = None
    return entity, normalized


def _summarize_mutation(entity_type: str, action: str, label: str) -> str:
    if entity_type == "loan":
        if action == "created":
            return f"Skapade lån: {label}."
        return f"Uppdaterade lån: {label}."
    if entity_type == "vehicle":
        if action == "created":
            return f"Skapade fordon: {label}."
        if action == "linked":
            return f"Kopplade fordon: {label}."
        return f"Uppdaterade fordon: {label}."
    if action == "skipped":
        return f"Hoppade över: {label}."
    return f"Applicerade {entity_type}: {label}."


def _apply_document_package(
    db: Session,
    *,
    document: models.Document,
    drafts: list[models.ExtractionDraft],
    request_body: schemas.DocumentApplyRequest,
) -> schemas.DocumentApplySummaryRead:
    if not drafts:
        raise HTTPException(status_code=400, detail="Dokumentet saknar utkast att applicera.")

    selected_ids = set(request_body.draft_ids or [draft.id for draft in drafts if draft.status in {"pending_review", "deferred"}])
    selected_drafts = [draft for draft in drafts if draft.id in selected_ids]
    if not selected_drafts:
        raise HTTPException(status_code=400, detail="Inga applicerbara utkast valdes.")

    resolution_map = {item.draft_id: item for item in _build_document_entity_resolutions(db, document, selected_drafts)}
    mutations: list[dict[str, Any]] = []
    manual_actions_required: list[str] = []
    applied_at = datetime.utcnow()

    try:
        for draft in selected_drafts:
            resolution = resolution_map.get(draft.id)
            selection = _pick_draft_action(request_body, draft, resolution)
            payload = _draft_review_payload(draft)

            if selection is None:
                manual_actions_required.append("Välj om lånet ska kopplas till befintligt lån eller skapas som nytt.")
                mutations.append(
                    {
                        "entity_type": "draft",
                        "action": "manual_review",
                        "entity_id": draft.id,
                        "label": f"Draft #{draft.id}",
                        "summary_sv": "Kräver att du väljer rätt lån innan något skrivs.",
                    }
                )
                continue

            if selection.action == "skip":
                draft.status = "rejected"
                draft.review_error = None
                draft.applied_at = applied_at
                mutations.append(
                    {
                        "entity_type": "draft",
                        "action": "skipped",
                        "entity_id": draft.id,
                        "label": f"Draft #{draft.id}",
                        "summary_sv": "Utkastet avvisades och skrevs inte till hushållets data.",
                    }
                )
                continue

            if draft.target_entity_type == "loan":
                proposed = dict(draft.proposed_json or {})
                if selection.proposed_json:
                    proposed.update(selection.proposed_json)
                proposed = _enrich_loan_payload(proposed, dict(draft.review_json or {}))
                if "household_id" not in proposed:
                    proposed["household_id"] = draft.household_id

                if selection.action == "link_existing":
                    loan_entity = get_object_or_404(db, models.Loan, selection.target_entity_id)
                    if loan_entity.household_id != draft.household_id:
                        raise HTTPException(status_code=400, detail="Lånet tillhör ett annat hushåll.")
                    loan_payload = schemas.LoanUpdate(**proposed)
                    for field, value in loan_payload.dict(exclude_unset=True, exclude_none=True).items():
                        setattr(loan_entity, field, value)
                    loan_action = "updated"
                else:
                    loan_payload = schemas.LoanCreate(**proposed)
                    loan_entity = models.Loan(**loan_payload.dict())
                    db.add(loan_entity)
                    db.flush()
                    loan_action = "created"

                loan_entity.statement_doc_id = document.id
                draft.status = "approved"
                draft.canonical_target_entity_type = "loan"
                draft.canonical_target_entity_id = loan_entity.id
                draft.review_error = None
                draft.applied_at = applied_at
                mutations.append(
                    {
                        "entity_type": "loan",
                        "action": loan_action,
                        "entity_id": loan_entity.id,
                        "label": _loan_display_label(loan_entity),
                        "summary_sv": _summarize_mutation("loan", loan_action, _loan_display_label(loan_entity)),
                    }
                )

                related_action = _pick_related_action(request_body, draft, resolution, payload)
                vehicle_label = _vehicle_label_from_payload(payload)
                if vehicle_label and related_action is None:
                    manual_actions_required.append("Bekräfta om dokumentet ska kopplas till befintligt fordon, skapa nytt fordon eller hoppas över.")
                    mutations.append(
                        {
                            "entity_type": "draft",
                            "action": "manual_review",
                            "entity_id": draft.id,
                            "label": vehicle_label,
                            "summary_sv": "Fordonet kräver manuell koppling innan hela objektkedjan är komplett.",
                        }
                    )
                elif vehicle_label and related_action is not None:
                    if related_action.action == "link_existing":
                        vehicle = get_object_or_404(db, models.Vehicle, related_action.target_entity_id)
                        if vehicle.household_id != draft.household_id:
                            raise HTTPException(status_code=400, detail="Fordonet tillhör ett annat hushåll.")
                        vehicle.loan_id = loan_entity.id
                        if loan_entity.person_id and vehicle.owner_person_id is None:
                            vehicle.owner_person_id = loan_entity.person_id
                        vehicle_action = "linked"
                    elif related_action.action == "create_new":
                        make, model = _split_vehicle_label(vehicle_label)
                        vehicle = models.Vehicle(
                            household_id=draft.household_id,
                            owner_person_id=loan_entity.person_id,
                            make=make,
                            model=model,
                            loan_id=loan_entity.id,
                            note=f"Skapad från dokument {document.file_name}",
                        )
                        db.add(vehicle)
                        db.flush()
                        vehicle_action = "created"
                    else:
                        mutations.append(
                            {
                                "entity_type": "vehicle",
                                "action": "skipped",
                                "entity_id": None,
                                "label": vehicle_label,
                                "summary_sv": _summarize_mutation("vehicle", "skipped", vehicle_label),
                            }
                        )
                        vehicle = None
                        vehicle_action = "skipped"

                    if vehicle_action in {"created", "linked"} and vehicle is not None:
                        mutations.append(
                            {
                                "entity_type": "vehicle",
                                "action": vehicle_action,
                                "entity_id": vehicle.id,
                                "label": _vehicle_display_label(vehicle),
                                "summary_sv": _summarize_mutation("vehicle", vehicle_action, _vehicle_display_label(vehicle)),
                            }
                        )
            else:
                entity, normalized = _apply_non_loan_draft(
                    db,
                    draft=draft,
                    document=document,
                    selection=selection,
                )
                draft.status = "approved"
                draft.canonical_target_entity_type = normalized
                draft.canonical_target_entity_id = entity.id
                draft.review_error = None
                draft.applied_at = applied_at
                mutations.append(
                    {
                        "entity_type": "draft",
                        "action": "created",
                        "entity_id": draft.id,
                        "label": draft.target_entity_type,
                        "summary_sv": f"Skapade {draft.target_entity_type} från dokumentet.",
                    }
                )

        summary_status = "manual_review"
        approved_any = any(draft.status == "approved" for draft in selected_drafts)
        if approved_any and manual_actions_required:
            summary_status = "partial"
        elif approved_any:
            summary_status = "applied"

        summary = schemas.DocumentApplySummaryRead(
            document_id=document.id,
            draft_id=selected_drafts[0].id if selected_drafts else None,
            status=summary_status,
            message_sv=(
                "Dokumentet applicerades till hushållets data."
                if summary_status == "applied"
                else "Dokumentet applicerades delvis. Några kopplingar kräver fortfarande manuell kontroll."
                if summary_status == "partial"
                else "Dokumentet kräver manuell koppling innan allt kan appliceras säkert."
            ),
            manual_actions_required=manual_actions_required,
            mutations=mutations,
            applied_at=applied_at,
        )
        summary_dict = summary.dict()
        summary_dict["applied_at"] = applied_at.isoformat()
        for draft in selected_drafts:
            draft.apply_summary_json = summary_dict
        _update_document_workflow_status(document)
        db.commit()
        return summary
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        for draft in selected_drafts:
            draft.status = "apply_failed"
            draft.review_error = str(exc)
        document.extraction_status = "failed"
        document.processing_error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Dokumentet kunde inte appliceras: {exc}") from exc


def _best_vehicle_for_loan(db: Session, household_id: int, vehicle_label: str | None) -> tuple[models.Vehicle | None, float]:
    if not vehicle_label:
        return None, 0.0
    alias_map = _load_alias_map(db, household_id)
    vehicles = db.query(models.Vehicle).filter_by(household_id=household_id).all()
    best_vehicle: models.Vehicle | None = None
    best_score = 0.0
    for vehicle in vehicles:
        score = _vehicle_match_score(vehicle, vehicle_label, alias_map)
        if score > best_score:
            best_vehicle = vehicle
            best_score = score
    return best_vehicle, round(best_score, 2)


def _upsert_vehicle_link_for_loan(
    db: Session,
    loan: models.Loan,
    *,
    household_id: int,
    review_payload: dict[str, Any],
    related_action: schemas.RelatedEntityApplySelection | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    manual_actions: list[str] = []
    vehicle_label = _vehicle_label_from_payload(review_payload)
    action = related_action.action if related_action is not None else None
    override_payload = dict(related_action.proposed_json or {}) if related_action is not None else {}

    if not vehicle_label:
        return (
            {
                "entity_type": "vehicle",
                "action": "skipped",
                "entity_id": None,
                "label": "Fordon",
                "summary_sv": "Dokumentet nämner inget tydligt fordon, så ingen fordonskoppling gjordes.",
            },
            manual_actions,
        )

    best_vehicle, confidence = _best_vehicle_for_loan(db, household_id, vehicle_label)
    make, model = _split_vehicle_label(vehicle_label)
    make = override_payload.get("make") or make
    model = override_payload.get("model") or model
    owner_person_id = override_payload.get("owner_person_id", loan.person_id)

    if action == "skip":
        return (
            {
                "entity_type": "vehicle",
                "action": "skipped",
                "entity_id": None,
                "label": vehicle_label,
                "summary_sv": "Fordonskopplingen hoppades över i detta steg.",
            },
            manual_actions,
        )

    if action == "link_existing":
        target_vehicle = get_object_or_404(db, models.Vehicle, related_action.target_entity_id)
        if target_vehicle.household_id != household_id:
            raise HTTPException(status_code=400, detail="Fordonet tillhör ett annat hushåll.")
        target_vehicle.loan_id = loan.id
        if not target_vehicle.make and make:
            target_vehicle.make = make
        if not target_vehicle.model and model:
            target_vehicle.model = model
        if not target_vehicle.owner_person_id and owner_person_id:
            target_vehicle.owner_person_id = owner_person_id
        return (
            {
                "entity_type": "vehicle",
                "action": "linked",
                "entity_id": target_vehicle.id,
                "label": _vehicle_display_label(target_vehicle),
                "summary_sv": "Kopplade valt fordon till lånet.",
            },
            manual_actions,
        )

    if action == "create_new":
        vehicle = models.Vehicle(
            household_id=household_id,
            owner_person_id=owner_person_id,
            make=make,
            model=model,
            loan_id=loan.id,
        )
        db.add(vehicle)
        db.flush()
        return (
            {
                "entity_type": "vehicle",
                "action": "created",
                "entity_id": vehicle.id,
                "label": _vehicle_display_label(vehicle),
                "summary_sv": "Skapade och kopplade ett nytt fordon utifrån dokumentets uppgifter.",
            },
            manual_actions,
        )

    if best_vehicle and confidence >= 0.75:
        best_vehicle.loan_id = loan.id
        if not best_vehicle.make and make:
            best_vehicle.make = make
        if not best_vehicle.model and model:
            best_vehicle.model = model
        return (
            {
                "entity_type": "vehicle",
                "action": "linked",
                "entity_id": best_vehicle.id,
                "label": _vehicle_display_label(best_vehicle),
                "summary_sv": f"Kopplade befintligt fordon till lånet med träffsäkerhet {round(confidence * 100)}%.",
            },
            manual_actions,
        )

    vehicle = models.Vehicle(
        household_id=household_id,
        owner_person_id=owner_person_id,
        make=make,
        model=model,
        loan_id=loan.id,
    )
    db.add(vehicle)
    db.flush()
    return (
        {
            "entity_type": "vehicle",
            "action": "created",
            "entity_id": vehicle.id,
            "label": _vehicle_display_label(vehicle),
            "summary_sv": "Skapade och kopplade ett nytt fordon utifrån dokumentets uppgifter.",
        },
        manual_actions,
    )


def _build_apply_summary(
    *,
    document: models.Document,
    draft: models.ExtractionDraft,
    mutations: list[dict[str, Any]],
    manual_actions_required: list[str],
    status: str,
    message_sv: str,
    applied_at: datetime,
) -> dict[str, Any]:
    return {
        "document_id": document.id,
        "draft_id": draft.id,
        "status": status,
        "message_sv": message_sv,
        "manual_actions_required": manual_actions_required,
        "mutations": mutations,
        "applied_at": applied_at.isoformat(),
    }


def _default_related_action_for_resolution(
    draft: models.ExtractionDraft,
    resolution: schemas.DocumentEntityResolutionRead | None,
) -> schemas.RelatedEntityApplySelection | None:
    if draft.target_entity_type != "loan":
        return None
    vehicle_label = _vehicle_label_from_payload(_draft_review_payload(draft))
    if not vehicle_label:
        return None
    best_vehicle = resolution.vehicle_candidates[0] if resolution and resolution.vehicle_candidates else None
    if best_vehicle and best_vehicle.entity_id is not None and (best_vehicle.confidence or 0.0) >= 0.75:
        return schemas.RelatedEntityApplySelection(
            source_draft_id=draft.id,
            entity_type="vehicle",
            action="link_existing",
            target_entity_id=best_vehicle.entity_id,
        )
    if resolution and resolution.vehicle_candidates:
        return None
    return schemas.RelatedEntityApplySelection(
        source_draft_id=draft.id,
        entity_type="vehicle",
        action="create_new",
    )


def _apply_single_draft(
    db: Session,
    draft: models.ExtractionDraft,
    document: models.Document,
    request_body: schemas.ExtractionDraftApplyRequest,
    related_action: schemas.RelatedEntityApplySelection | None = None,
) -> dict[str, Any]:
    (schema_class, model_class), normalized = draft_target_config(draft.target_entity_type)
    proposed = dict(draft.proposed_json or {})
    review_payload = dict(draft.review_json or {})
    if request_body.proposed_json:
        proposed.update(request_body.proposed_json)
    if normalized == "loan":
        proposed = _enrich_loan_payload(proposed, review_payload)
    if "household_id" in getattr(schema_class, "__fields__", {}) and "household_id" not in proposed:
        proposed["household_id"] = draft.household_id

    mutations: list[dict[str, Any]] = []
    manual_actions_required: list[str] = []
    now = datetime.utcnow()

    try:
        if request_body.action == "link_existing":
            if normalized != "loan":
                raise HTTPException(status_code=400, detail="Befintlig koppling stöds bara för lån i nuvarande review-flöde.")
            entity = get_object_or_404(db, models.Loan, request_body.target_entity_id)
            if entity.household_id != draft.household_id:
                raise HTTPException(status_code=400, detail="Lånet tillhör ett annat hushåll.")
            payload = schemas.LoanUpdate(**proposed)
            update_data = payload.dict(exclude_unset=True, exclude_none=True)
            for field, value in update_data.items():
                setattr(entity, field, value)
            mutations.append(
                {
                    "entity_type": "loan",
                    "action": "updated",
                    "entity_id": entity.id,
                    "label": _loan_display_label(entity),
                    "summary_sv": "Uppdaterade befintligt lån med dokumentets fält.",
                }
            )
        else:
            payload = schema_class(**proposed)
            entity = model_class(**payload.dict())
            db.add(entity)
            db.flush()
            mutations.append(
                {
                    "entity_type": normalized,
                    "action": "created",
                    "entity_id": entity.id,
                    "label": _canonical_target_label(normalized, entity),
                    "summary_sv": "Skapade en ny kanonisk post från dokumentet.",
                }
            )

        if normalized == "loan":
            vehicle_mutation, vehicle_manual_actions = _upsert_vehicle_link_for_loan(
                db,
                entity,
                household_id=draft.household_id,
                review_payload=review_payload,
                related_action=related_action,
            )
            if vehicle_mutation is not None:
                mutations.append(vehicle_mutation)
            manual_actions_required.extend(vehicle_manual_actions)
            entity.statement_doc_id = document.id

        draft.status = "approved"
        draft.canonical_target_entity_type = normalized
        draft.canonical_target_entity_id = entity.id
        draft.review_error = None
        draft.applied_at = now
        draft.apply_summary_json = _build_apply_summary(
            document=document,
            draft=draft,
            mutations=mutations,
            manual_actions_required=manual_actions_required,
            status="partial" if manual_actions_required else "applied",
            message_sv="Dokumentet applicerades."
            if not manual_actions_required
            else "Dokumentet applicerades men kräver en manuell fordonskoppling.",
            applied_at=now,
        )
        _update_document_workflow_status(document)
        return {
            "draft_id": draft.id,
            "target_entity_type": normalized,
            "target_entity_id": entity.id,
            "status": draft.status,
            "summary": draft.apply_summary_json["message_sv"],
            "applied_entities": mutations,
            "manual_actions_required": manual_actions_required,
        }
    except HTTPException:
        raise
    except Exception as exc:
        draft.status = "apply_failed"
        draft.review_error = str(exc)
        document.extraction_status = "failed"
        document.processing_error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Draft kunde inte appliceras: {exc}") from exc


def upload_to_disk(household_id: int, file: UploadFile) -> tuple[str, str, bytes]:
    household_dir = UPLOAD_ROOT / str(household_id)
    household_dir.mkdir(parents=True, exist_ok=True)
    raw = file.file.read()
    checksum = hashlib.sha256(raw).hexdigest()
    safe_name = f"{uuid4().hex}_{Path(file.filename or 'document.bin').name}"
    destination = household_dir / safe_name
    destination.write_bytes(raw)
    return str(destination.resolve()), checksum, raw


def draft_target_config(target_entity_type: str):
    mapping = {
        "person": (schemas.PersonCreate, models.Person),
        "income_source": (schemas.IncomeSourceCreate, models.IncomeSource),
        "loan": (schemas.LoanCreate, models.Loan),
        "recurring_cost": (schemas.RecurringCostCreate, models.RecurringCost),
        "subscription_contract": (schemas.SubscriptionContractCreate, models.SubscriptionContract),
        "insurance_policy": (schemas.InsurancePolicyCreate, models.InsurancePolicy),
        "vehicle": (schemas.VehicleCreate, models.Vehicle),
        "asset": (schemas.AssetCreate, models.Asset),
        "housing_scenario": (schemas.HousingScenarioCreate, models.HousingScenario),
        "document": (schemas.DocumentCreate, models.Document),
        "optimization_opportunity": (schemas.OptimizationOpportunityCreate, models.OptimizationOpportunity),
        "scenario": (schemas.ScenarioCreate, models.Scenario),
        "scenario_result": (schemas.ScenarioResultCreate, models.ScenarioResult),
        "report_snapshot": (schemas.ReportSnapshotCreate, models.ReportSnapshot),
    }
    normalized = target_entity_type.strip().lower()
    if normalized not in mapping:
        raise HTTPException(status_code=400, detail=f"Unsupported draft target_entity_type: {target_entity_type}")
    return mapping[normalized], normalized

def create_or_get_opportunity(
    db: Session,
    household_id: int,
    *,
    kind: str,
    target_entity_type: str,
    target_entity_id: int,
    title: str,
    rationale: str,
    estimated_monthly_saving: float,
    confidence: float,
):
    existing = (
        db.query(models.OptimizationOpportunity)
        .filter_by(
            household_id=household_id,
            kind=kind,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            title=title,
            status="open",
        )
        .first()
    )
    if existing:
        return existing

    opportunity = models.OptimizationOpportunity(
        household_id=household_id,
        kind=kind,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        title=title,
        rationale=rationale,
        estimated_monthly_saving=round(estimated_monthly_saving, 2),
        estimated_yearly_saving=round(estimated_monthly_saving * 12, 2),
        confidence=confidence,
        effort_level="medium",
        risk_level="low" if kind == "cancel" else "medium",
        reversibility="high",
        status="open",
    )
    db.add(opportunity)
    db.flush()
    return opportunity


# --- Household Endpoints ---
@app.get("/households", response_model=List[schemas.HouseholdRead])
def list_households(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    allowed_household_id = _request_household_id(request, db)
    query = db.query(models.Household)
    if allowed_household_id is not None:
        query = query.filter(models.Household.id == allowed_household_id)
    return query.offset(skip).limit(limit).all()


@app.post("/households", response_model=schemas.HouseholdRead, status_code=status.HTTP_201_CREATED)
def create_household(household: schemas.HouseholdCreate, db: Session = Depends(get_db)):
    db_household = models.Household(**household.dict())
    db.add(db_household)
    db.commit()
    db.refresh(db_household)
    return db_household


@app.get("/households/{household_id}", response_model=schemas.HouseholdRead)
def read_household(household_id: int, request: Request, db: Session = Depends(get_db)):
    return ensure_household_exists(db, household_id, request)


@app.put("/households/{household_id}", response_model=schemas.HouseholdRead)
def update_household(household_id: int, household: schemas.HouseholdUpdate, request: Request, db: Session = Depends(get_db)):
    db_household = ensure_household_exists(db, household_id, request)
    for field, value in household.dict(exclude_unset=True).items():
        setattr(db_household, field, value)
    db.commit()
    db.refresh(db_household)
    return db_household


@app.delete("/households/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_household(household_id: int, request: Request, db: Session = Depends(get_db)):
    db_household = ensure_household_exists(db, household_id, request)
    db.delete(db_household)
    db.commit()
    return


@app.get("/households/{household_id}/summary", response_model=schemas.HouseholdSummaryRead)
def get_household_summary(household_id: int, request: Request, db: Session = Depends(get_db)):
    ensure_household_exists(db, household_id, request)
    return calculations.build_household_summary(calculations.load_household_records(db, household_id), household_id)


@app.post("/households/{household_id}/report_snapshots/generate", response_model=schemas.ReportSnapshotRead)
def generate_household_report_snapshot(
    household_id: int,
    request: schemas.ReportGenerateRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, http_request)
    summary = calculations.build_household_summary(calculations.load_household_records(db, household_id), household_id)
    snapshot = models.ReportSnapshot(
        household_id=household_id,
        type=request.type,
        as_of_date=request.as_of_date or date.today(),
        assumption_json=request.assumption_json,
        result_json=summary,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@app.get("/households/{household_id}/export/bank_pdf")
def export_bank_pdf(household_id: int, request: Request, db: Session = Depends(get_db)):
    ensure_household_exists(db, household_id, request)
    pdf_bytes = pdf_export.generate_bank_pdf(db, household_id)
    household = db.get(models.Household, household_id)
    filename = f"bankkalkyl-{household.name.lower().replace(' ', '-')}-{date.today().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/households/{household_id}/optimization_scan", response_model=List[schemas.OptimizationOpportunityRead])
def optimization_scan(household_id: int, request: Request, db: Session = Depends(get_db)):
    ensure_household_exists(db, household_id, request)
    results = []

    subscriptions = db.query(models.SubscriptionContract).filter_by(household_id=household_id).all()
    for subscription in subscriptions:
        if subscription.ordinary_cost and subscription.current_monthly_cost and subscription.ordinary_cost > subscription.current_monthly_cost:
            results.append(
                create_or_get_opportunity(
                    db,
                    household_id,
                    kind="renegotiate",
                    target_entity_type="subscription_contract",
                    target_entity_id=subscription.id,
                    title=f"Review {subscription.provider} pricing",
                    rationale="Ordinary price is above current price and likely worth renegotiating.",
                    estimated_monthly_saving=subscription.ordinary_cost - subscription.current_monthly_cost,
                    confidence=0.72,
                )
            )
        if subscription.household_criticality == "optional" and (subscription.current_monthly_cost or 0) > 0:
            results.append(
                create_or_get_opportunity(
                    db,
                    household_id,
                    kind="cancel",
                    target_entity_type="subscription_contract",
                    target_entity_id=subscription.id,
                    title=f"Cancel optional subscription: {subscription.provider}",
                    rationale="Marked optional and contributes recurring monthly cost.",
                    estimated_monthly_saving=subscription.current_monthly_cost,
                    confidence=0.61,
                )
            )

    recurring_costs = db.query(models.RecurringCost).filter_by(household_id=household_id).all()
    for cost in recurring_costs:
        if cost.controllability in {models.Controllability.reducible, models.Controllability.discretionary}:
            monthly_amount = calculations.amount_to_monthly(cost.amount, cost.frequency)
            if monthly_amount > 0:
                results.append(
                    create_or_get_opportunity(
                        db,
                        household_id,
                        kind="reduce_usage",
                        target_entity_type="recurring_cost",
                        target_entity_id=cost.id,
                        title=f"Reduce {cost.category}",
                        rationale="Cost is marked reducible/discretionary.",
                        estimated_monthly_saving=monthly_amount * 0.15,
                        confidence=0.55,
                    )
                )

    db.commit()
    for item in results:
        db.refresh(item)
    return results


# --- Person Endpoints ---
@app.get("/persons", response_model=List[schemas.PersonRead])
def list_persons(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Person).offset(skip).limit(limit).all()


@app.post("/persons", response_model=schemas.PersonRead, status_code=status.HTTP_201_CREATED)
def create_person(person: schemas.PersonCreate, db: Session = Depends(get_db)):
    db_person = models.Person(**person.dict())
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    return db_person


@app.get("/persons/{person_id}", response_model=schemas.PersonRead)
def read_person(person_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.Person, person_id)


@app.put("/persons/{person_id}", response_model=schemas.PersonRead)
def update_person(person_id: int, person: schemas.PersonUpdate, db: Session = Depends(get_db)):
    db_person = get_object_or_404(db, models.Person, person_id)
    for field, value in person.dict(exclude_unset=True).items():
        setattr(db_person, field, value)
    db.commit()
    db.refresh(db_person)
    return db_person


@app.delete("/persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: int, db: Session = Depends(get_db)):
    db_person = get_object_or_404(db, models.Person, person_id)
    db.delete(db_person)
    db.commit()
    return


# --- IncomeSource Endpoints ---
@app.get("/income_sources", response_model=List[schemas.IncomeSourceRead])
def list_income_sources(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.IncomeSource).offset(skip).limit(limit).all()


@app.post("/income_sources", response_model=schemas.IncomeSourceRead, status_code=status.HTTP_201_CREATED)
def create_income_source(income_source: schemas.IncomeSourceCreate, db: Session = Depends(get_db)):
    db_income = models.IncomeSource(**income_source.dict())
    db.add(db_income)
    db.commit()
    db.refresh(db_income)
    return db_income


@app.get("/income_sources/{income_id}", response_model=schemas.IncomeSourceRead)
def read_income_source(income_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.IncomeSource, income_id)


@app.put("/income_sources/{income_id}", response_model=schemas.IncomeSourceRead)
def update_income_source(income_id: int, income_source: schemas.IncomeSourceUpdate, db: Session = Depends(get_db)):
    db_income = get_object_or_404(db, models.IncomeSource, income_id)
    for field, value in income_source.dict(exclude_unset=True).items():
        setattr(db_income, field, value)
    db.commit()
    db.refresh(db_income)
    return db_income


@app.delete("/income_sources/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income_source(income_id: int, db: Session = Depends(get_db)):
    db_income = get_object_or_404(db, models.IncomeSource, income_id)
    db.delete(db_income)
    db.commit()
    return


# --- Loan Endpoints ---
@app.get("/loans", response_model=List[schemas.LoanRead])
def list_loans(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Loan).offset(skip).limit(limit).all()


@app.post("/loans", response_model=schemas.LoanRead, status_code=status.HTTP_201_CREATED)
def create_loan(loan: schemas.LoanCreate, db: Session = Depends(get_db)):
    db_loan = models.Loan(**loan.dict())
    db.add(db_loan)
    db.commit()
    db.refresh(db_loan)
    return db_loan


@app.get("/loans/{loan_id}", response_model=schemas.LoanRead)
def read_loan(loan_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.Loan, loan_id)


@app.put("/loans/{loan_id}", response_model=schemas.LoanRead)
def update_loan(loan_id: int, loan: schemas.LoanUpdate, db: Session = Depends(get_db)):
    db_loan = get_object_or_404(db, models.Loan, loan_id)
    for field, value in loan.dict(exclude_unset=True).items():
        setattr(db_loan, field, value)
    db.commit()
    db.refresh(db_loan)
    return db_loan


@app.delete("/loans/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loan(loan_id: int, db: Session = Depends(get_db)):
    db_loan = get_object_or_404(db, models.Loan, loan_id)
    db.delete(db_loan)
    db.commit()
    return


# --- RecurringCost Endpoints ---
@app.get("/recurring_costs", response_model=List[schemas.RecurringCostRead])
def list_recurring_costs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.RecurringCost).offset(skip).limit(limit).all()


@app.post("/recurring_costs", response_model=schemas.RecurringCostRead, status_code=status.HTTP_201_CREATED)
def create_recurring_cost(cost: schemas.RecurringCostCreate, db: Session = Depends(get_db)):
    db_cost = models.RecurringCost(**cost.dict())
    db.add(db_cost)
    db.commit()
    db.refresh(db_cost)
    return db_cost


@app.get("/recurring_costs/{cost_id}", response_model=schemas.RecurringCostRead)
def read_recurring_cost(cost_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.RecurringCost, cost_id)


@app.put("/recurring_costs/{cost_id}", response_model=schemas.RecurringCostRead)
def update_recurring_cost(cost_id: int, cost: schemas.RecurringCostUpdate, db: Session = Depends(get_db)):
    db_cost = get_object_or_404(db, models.RecurringCost, cost_id)
    for field, value in cost.dict(exclude_unset=True).items():
        setattr(db_cost, field, value)
    db.commit()
    db.refresh(db_cost)
    return db_cost


@app.delete("/recurring_costs/{cost_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_cost(cost_id: int, db: Session = Depends(get_db)):
    db_cost = get_object_or_404(db, models.RecurringCost, cost_id)
    db.delete(db_cost)
    db.commit()
    return


# --- SubscriptionContract Endpoints ---
@app.get("/subscription_contracts", response_model=List[schemas.SubscriptionContractRead])
def list_subscription_contracts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.SubscriptionContract).offset(skip).limit(limit).all()


@app.post(
    "/subscription_contracts",
    response_model=schemas.SubscriptionContractRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription_contract(contract: schemas.SubscriptionContractCreate, db: Session = Depends(get_db)):
    db_contract = models.SubscriptionContract(**contract.dict())
    db.add(db_contract)
    db.commit()
    db.refresh(db_contract)
    return db_contract


@app.get("/subscription_contracts/{contract_id}", response_model=schemas.SubscriptionContractRead)
def read_subscription_contract(contract_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.SubscriptionContract, contract_id)


@app.put("/subscription_contracts/{contract_id}", response_model=schemas.SubscriptionContractRead)
def update_subscription_contract(contract_id: int, contract: schemas.SubscriptionContractUpdate, db: Session = Depends(get_db)):
    db_contract = get_object_or_404(db, models.SubscriptionContract, contract_id)
    for field, value in contract.dict(exclude_unset=True).items():
        setattr(db_contract, field, value)
    db.commit()
    db.refresh(db_contract)
    return db_contract


@app.delete("/subscription_contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription_contract(contract_id: int, db: Session = Depends(get_db)):
    db_contract = get_object_or_404(db, models.SubscriptionContract, contract_id)
    db.delete(db_contract)
    db.commit()
    return


# --- InsurancePolicy Endpoints ---
@app.get("/insurance_policies", response_model=List[schemas.InsurancePolicyRead])
def list_insurance_policies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.InsurancePolicy).offset(skip).limit(limit).all()


@app.post(
    "/insurance_policies",
    response_model=schemas.InsurancePolicyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_insurance_policy(policy: schemas.InsurancePolicyCreate, db: Session = Depends(get_db)):
    db_policy = models.InsurancePolicy(**policy.dict())
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy


@app.get("/insurance_policies/{policy_id}", response_model=schemas.InsurancePolicyRead)
def read_insurance_policy(policy_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.InsurancePolicy, policy_id)


@app.put("/insurance_policies/{policy_id}", response_model=schemas.InsurancePolicyRead)
def update_insurance_policy(policy_id: int, policy: schemas.InsurancePolicyUpdate, db: Session = Depends(get_db)):
    db_policy = get_object_or_404(db, models.InsurancePolicy, policy_id)
    for field, value in policy.dict(exclude_unset=True).items():
        setattr(db_policy, field, value)
    db.commit()
    db.refresh(db_policy)
    return db_policy


@app.delete("/insurance_policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_insurance_policy(policy_id: int, db: Session = Depends(get_db)):
    db_policy = get_object_or_404(db, models.InsurancePolicy, policy_id)
    db.delete(db_policy)
    db.commit()
    return


# --- Vehicle Endpoints ---
@app.get("/vehicles", response_model=List[schemas.VehicleRead])
def list_vehicles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Vehicle).offset(skip).limit(limit).all()


@app.post("/vehicles", response_model=schemas.VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(vehicle: schemas.VehicleCreate, db: Session = Depends(get_db)):
    db_vehicle = models.Vehicle(**vehicle.dict())
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


@app.get("/vehicles/{vehicle_id}", response_model=schemas.VehicleRead)
def read_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.Vehicle, vehicle_id)


@app.put("/vehicles/{vehicle_id}", response_model=schemas.VehicleRead)
def update_vehicle(vehicle_id: int, vehicle: schemas.VehicleUpdate, db: Session = Depends(get_db)):
    db_vehicle = get_object_or_404(db, models.Vehicle, vehicle_id)
    for field, value in vehicle.dict(exclude_unset=True).items():
        setattr(db_vehicle, field, value)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


@app.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    db_vehicle = get_object_or_404(db, models.Vehicle, vehicle_id)
    db.delete(db_vehicle)
    db.commit()
    return


# --- Asset Endpoints ---
@app.get("/financial_assets", response_model=List[schemas.AssetRead])
def list_assets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Asset).offset(skip).limit(limit).all()


@app.post("/financial_assets", response_model=schemas.AssetRead, status_code=status.HTTP_201_CREATED)
def create_asset(asset: schemas.AssetCreate, db: Session = Depends(get_db)):
    db_asset = models.Asset(**asset.dict())
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    return db_asset


@app.get("/financial_assets/{asset_id}", response_model=schemas.AssetRead)
def read_asset(asset_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.Asset, asset_id)


@app.put("/financial_assets/{asset_id}", response_model=schemas.AssetRead)
def update_asset(asset_id: int, asset: schemas.AssetUpdate, db: Session = Depends(get_db)):
    db_asset = get_object_or_404(db, models.Asset, asset_id)
    for field, value in asset.dict(exclude_unset=True).items():
        setattr(db_asset, field, value)
    db.commit()
    db.refresh(db_asset)
    return db_asset


@app.delete("/financial_assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, db: Session = Depends(get_db)):
    db_asset = get_object_or_404(db, models.Asset, asset_id)
    db.delete(db_asset)
    db.commit()
    return


# --- HousingScenario Endpoints ---
@app.get("/housing_scenarios", response_model=List[schemas.HousingScenarioRead])
def list_housing_scenarios(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.HousingScenario).offset(skip).limit(limit).all()


@app.post("/housing_scenarios", response_model=schemas.HousingScenarioRead, status_code=status.HTTP_201_CREATED)
def create_housing_scenario(scenario: schemas.HousingScenarioCreate, db: Session = Depends(get_db)):
    db_scenario = models.HousingScenario(**scenario.dict())
    db.add(db_scenario)
    db.commit()
    db.refresh(db_scenario)
    return db_scenario


@app.get("/housing_scenarios/{scenario_id}", response_model=schemas.HousingScenarioRead)
def read_housing_scenario(scenario_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.HousingScenario, scenario_id)


@app.put("/housing_scenarios/{scenario_id}", response_model=schemas.HousingScenarioRead)
def update_housing_scenario(scenario_id: int, scenario: schemas.HousingScenarioUpdate, db: Session = Depends(get_db)):
    db_scenario = get_object_or_404(db, models.HousingScenario, scenario_id)
    for field, value in scenario.dict(exclude_unset=True).items():
        setattr(db_scenario, field, value)
    db.commit()
    db.refresh(db_scenario)
    return db_scenario


@app.delete("/housing_scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_housing_scenario(scenario_id: int, db: Session = Depends(get_db)):
    db_scenario = get_object_or_404(db, models.HousingScenario, scenario_id)
    db.delete(db_scenario)
    db.commit()
    return


# --- Document Endpoints ---
@app.get("/documents", response_model=List[schemas.DocumentRead])
def list_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Document).offset(skip).limit(limit).all()


@app.post("/documents", response_model=schemas.DocumentRead, status_code=status.HTTP_201_CREATED)
def create_document(document: schemas.DocumentCreate, db: Session = Depends(get_db)):
    db_doc = models.Document(**document.dict())
    if db_doc.extraction_status not in DOCUMENT_WORKFLOW_STATUS:
        db_doc.extraction_status = "interpreted" if db_doc.extracted_text else "uploaded"
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc


@app.post("/documents/upload", response_model=schemas.DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(
    household_id: int = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    issuer: str | None = Form(None),
    currency: str | None = Form(None),
    extracted_text: str | None = Form(None),
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id)
    storage_path, checksum, raw = upload_to_disk(household_id, file)
    extracted_payload = normalize_ingest_text(extracted_text) if extracted_text and extracted_text.strip() else None
    extraction_mode = "user_provided"
    if extracted_payload is None:
        auto_extracted = extract_text_from_upload(raw, file_name=file.filename, mime_type=file.content_type)
        extracted_payload = auto_extracted.text
        extraction_mode = auto_extracted.extraction_mode
    extraction_status, processing_error = _status_for_uploaded_document(extracted_payload, extraction_mode)
    document = models.Document(
        household_id=household_id,
        document_type=document_type,
        file_name=file.filename or "uploaded-file",
        mime_type=file.content_type,
        checksum=checksum,
        issuer=issuer,
        currency=currency,
        extracted_text=extracted_payload,
        extraction_status=extraction_status,
        processing_error=processing_error,
        storage_path=storage_path,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@app.get("/documents/{doc_id}", response_model=schemas.DocumentRead)
def read_document(doc_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.Document, doc_id)


@app.get("/documents/{doc_id}/review", response_model=schemas.DocumentWorkflowRead)
def read_document_review(doc_id: int, db: Session = Depends(get_db)):
    document = get_object_or_404(db, models.Document, doc_id)
    return _build_document_workflow_read(db, document)


@app.post("/documents/{doc_id}/apply", response_model=schemas.DocumentApplyResponse)
def apply_document_review(
    doc_id: int,
    request_body: schemas.DocumentApplyRequest | None = Body(None),
    db: Session = Depends(get_db),
):
    document = get_object_or_404(db, models.Document, doc_id)
    request_body = request_body or schemas.DocumentApplyRequest()
    drafts = (
        db.query(models.ExtractionDraft)
        .filter_by(document_id=document.id)
        .order_by(models.ExtractionDraft.created_at.asc())
        .all()
    )
    summary = _apply_document_package(
        db,
        document=document,
        drafts=drafts,
        request_body=request_body,
    )
    db.refresh(document)
    workflow = _build_document_workflow_read(db, document)
    return schemas.DocumentApplyResponse(
        document_id=document.id,
        workflow_status=workflow.workflow_status,
        status_label_sv=workflow.status_label_sv,
        apply_summary=summary,
        workflow=workflow,
    )


@app.get("/documents/{doc_id}/download", include_in_schema=False)
def download_document(doc_id: int, db: Session = Depends(get_db)):
    document = get_object_or_404(db, models.Document, doc_id)
    if not document.storage_path:
        raise HTTPException(status_code=404, detail="Document has no stored file")
    file_path = Path(document.storage_path)
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found")
    return FileResponse(file_path, filename=document.file_name, media_type=document.mime_type)


@app.put("/documents/{doc_id}", response_model=schemas.DocumentRead)
def update_document(doc_id: int, document: schemas.DocumentUpdate, db: Session = Depends(get_db)):
    db_doc = get_object_or_404(db, models.Document, doc_id)
    for field, value in document.dict(exclude_unset=True).items():
        setattr(db_doc, field, value)
    if db_doc.extraction_status not in DOCUMENT_WORKFLOW_STATUS:
        db_doc.extraction_status = "interpreted" if db_doc.extracted_text else "uploaded"
    db.commit()
    db.refresh(db_doc)
    return db_doc


@app.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    db_doc = get_object_or_404(db, models.Document, doc_id)
    db.delete(db_doc)
    db.commit()
    return


# --- ExtractionDraft Endpoints ---
@app.get("/extraction_drafts", response_model=List[schemas.ExtractionDraftRead])
def list_extraction_drafts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.ExtractionDraft).offset(skip).limit(limit).all()


@app.post("/extraction_drafts", response_model=schemas.ExtractionDraftRead, status_code=status.HTTP_201_CREATED)
def create_extraction_draft(draft: schemas.ExtractionDraftCreate, db: Session = Depends(get_db)):
    db_draft = models.ExtractionDraft(**draft.dict())
    db.add(db_draft)
    document = get_object_or_404(db, models.Document, draft.document_id)
    document.extraction_status = "pending_review"
    document.processing_error = None
    db.commit()
    db.refresh(db_draft)
    return db_draft


@app.get("/extraction_drafts/{draft_id}", response_model=schemas.ExtractionDraftRead)
def read_extraction_draft(draft_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.ExtractionDraft, draft_id)


@app.put("/extraction_drafts/{draft_id}", response_model=schemas.ExtractionDraftRead)
def update_extraction_draft(draft_id: int, draft: schemas.ExtractionDraftUpdate, db: Session = Depends(get_db)):
    db_draft = get_object_or_404(db, models.ExtractionDraft, draft_id)
    for field, value in draft.dict(exclude_unset=True).items():
        setattr(db_draft, field, value)
    document = get_object_or_404(db, models.Document, db_draft.document_id)
    _update_document_workflow_status(document)
    db.commit()
    db.refresh(db_draft)
    return db_draft


@app.post("/extraction_drafts/{draft_id}/apply", response_model=schemas.ExtractionApplyRead)
def apply_extraction_draft(
    draft_id: int,
    request_body: schemas.ExtractionDraftApplyRequest | None = Body(None),
    db: Session = Depends(get_db),
):
    draft = get_object_or_404(db, models.ExtractionDraft, draft_id)
    if draft.status == "approved":
        raise HTTPException(status_code=400, detail="Draft already approved")
    request_body = request_body or schemas.ExtractionDraftApplyRequest()
    document = get_object_or_404(db, models.Document, draft.document_id)
    try:
        response_payload = _apply_single_draft(db, draft, document, request_body)
        db.commit()
        db.refresh(draft)
        db.refresh(document)
        return response_payload
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        draft.status = "apply_failed"
        draft.review_error = str(exc)
        document.extraction_status = "failed"
        document.processing_error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Draft kunde inte appliceras: {exc}") from exc


@app.delete("/extraction_drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_extraction_draft(draft_id: int, db: Session = Depends(get_db)):
    db_draft = get_object_or_404(db, models.ExtractionDraft, draft_id)
    document = get_object_or_404(db, models.Document, db_draft.document_id)
    db.delete(db_draft)
    db.flush()
    _update_document_workflow_status(document)
    db.commit()
    return


# --- OptimizationOpportunity Endpoints ---
@app.get("/optimization_opportunities", response_model=List[schemas.OptimizationOpportunityRead])
def list_optimization_opportunities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.OptimizationOpportunity).offset(skip).limit(limit).all()


@app.post(
    "/optimization_opportunities",
    response_model=schemas.OptimizationOpportunityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_optimization_opportunity(op: schemas.OptimizationOpportunityCreate, db: Session = Depends(get_db)):
    db_op = models.OptimizationOpportunity(**op.dict())
    db.add(db_op)
    db.commit()
    db.refresh(db_op)
    return db_op


@app.get("/optimization_opportunities/{op_id}", response_model=schemas.OptimizationOpportunityRead)
def read_optimization_opportunity(op_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.OptimizationOpportunity, op_id)


@app.put("/optimization_opportunities/{op_id}", response_model=schemas.OptimizationOpportunityRead)
def update_optimization_opportunity(op_id: int, op: schemas.OptimizationOpportunityUpdate, db: Session = Depends(get_db)):
    db_op = get_object_or_404(db, models.OptimizationOpportunity, op_id)
    for field, value in op.dict(exclude_unset=True).items():
        setattr(db_op, field, value)
    db.commit()
    db.refresh(db_op)
    return db_op


@app.delete("/optimization_opportunities/{op_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_optimization_opportunity(op_id: int, db: Session = Depends(get_db)):
    db_op = get_object_or_404(db, models.OptimizationOpportunity, op_id)
    db.delete(db_op)
    db.commit()
    return


# --- Scenario Endpoints ---
@app.get("/scenarios", response_model=List[schemas.ScenarioRead])
def list_scenarios(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Scenario).offset(skip).limit(limit).all()


@app.post("/scenarios", response_model=schemas.ScenarioRead, status_code=status.HTTP_201_CREATED)
def create_scenario(scenario: schemas.ScenarioCreate, db: Session = Depends(get_db)):
    db_scenario = models.Scenario(**scenario.dict())
    db.add(db_scenario)
    db.commit()
    db.refresh(db_scenario)
    return db_scenario


@app.get("/scenarios/{scenario_id}", response_model=schemas.ScenarioRead)
def read_scenario(scenario_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.Scenario, scenario_id)


@app.post("/scenarios/{scenario_id}/run", response_model=schemas.ScenarioResultRead)
def run_scenario(scenario_id: int, db: Session = Depends(get_db)):
    scenario = get_object_or_404(db, models.Scenario, scenario_id)
    baseline_records = calculations.load_household_records(db, scenario.household_id)
    projected_records = calculations.apply_scenario_adjustments(
        baseline_records, list((scenario.change_set_json or {}).get("adjustments", []))
    )
    baseline_summary = calculations.build_household_summary(baseline_records, scenario.household_id)
    projected_summary = calculations.build_household_summary(projected_records, scenario.household_id)

    result = models.ScenarioResult(
        household_id=scenario.household_id,
        scenario_id=scenario.id,
        result_json={
            "baseline": baseline_summary,
            "projected": projected_summary,
            "adjustments": list((scenario.change_set_json or {}).get("adjustments", [])),
        },
        monthly_delta=round(projected_summary["monthly_net_cashflow"] - baseline_summary["monthly_net_cashflow"], 2),
        yearly_delta=round(projected_summary["yearly_net_cashflow"] - baseline_summary["yearly_net_cashflow"], 2),
        liquidity_delta=round(projected_summary["asset_liquid_value"] - baseline_summary["asset_liquid_value"], 2),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


@app.put("/scenarios/{scenario_id}", response_model=schemas.ScenarioRead)
def update_scenario(scenario_id: int, scenario: schemas.ScenarioUpdate, db: Session = Depends(get_db)):
    db_scenario = get_object_or_404(db, models.Scenario, scenario_id)
    for field, value in scenario.dict(exclude_unset=True).items():
        setattr(db_scenario, field, value)
    db.commit()
    db.refresh(db_scenario)
    return db_scenario


@app.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    db_scenario = get_object_or_404(db, models.Scenario, scenario_id)
    db.delete(db_scenario)
    db.commit()
    return


# --- ScenarioResult Endpoints ---
@app.get("/scenario_results", response_model=List[schemas.ScenarioResultRead])
def list_scenario_results(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.ScenarioResult).offset(skip).limit(limit).all()


@app.post("/scenario_results", response_model=schemas.ScenarioResultRead, status_code=status.HTTP_201_CREATED)
def create_scenario_result(result: schemas.ScenarioResultCreate, db: Session = Depends(get_db)):
    db_result = models.ScenarioResult(**result.dict())
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


@app.get("/scenario_results/{result_id}", response_model=schemas.ScenarioResultRead)
def read_scenario_result(result_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.ScenarioResult, result_id)


@app.put("/scenario_results/{result_id}", response_model=schemas.ScenarioResultRead)
def update_scenario_result(result_id: int, result: schemas.ScenarioResultUpdate, db: Session = Depends(get_db)):
    db_result = get_object_or_404(db, models.ScenarioResult, result_id)
    for field, value in result.dict(exclude_unset=True).items():
        setattr(db_result, field, value)
    db.commit()
    db.refresh(db_result)
    return db_result


@app.delete("/scenario_results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario_result(result_id: int, db: Session = Depends(get_db)):
    db_result = get_object_or_404(db, models.ScenarioResult, result_id)
    db.delete(db_result)
    db.commit()
    return


# --- ReportSnapshot Endpoints ---
@app.get("/report_snapshots", response_model=List[schemas.ReportSnapshotRead])
def list_report_snapshots(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.ReportSnapshot).offset(skip).limit(limit).all()


@app.post(
    "/report_snapshots",
    response_model=schemas.ReportSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def create_report_snapshot(snapshot: schemas.ReportSnapshotCreate, db: Session = Depends(get_db)):
    db_snapshot = models.ReportSnapshot(**snapshot.dict())
    db.add(db_snapshot)
    db.commit()
    db.refresh(db_snapshot)
    return db_snapshot


@app.get("/report_snapshots/{snapshot_id}", response_model=schemas.ReportSnapshotRead)
def read_report_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    return get_object_or_404(db, models.ReportSnapshot, snapshot_id)


@app.put("/report_snapshots/{snapshot_id}", response_model=schemas.ReportSnapshotRead)
def update_report_snapshot(snapshot_id: int, snapshot: schemas.ReportSnapshotUpdate, db: Session = Depends(get_db)):
    db_snapshot = get_object_or_404(db, models.ReportSnapshot, snapshot_id)
    for field, value in snapshot.dict(exclude_unset=True).items():
        setattr(db_snapshot, field, value)
    db.commit()
    db.refresh(db_snapshot)
    return db_snapshot


@app.delete("/report_snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    db_snapshot = get_object_or_404(db, models.ReportSnapshot, snapshot_id)
    db.delete(db_snapshot)
    db.commit()
    return


# --- Merchant Alias Endpoints ---
@app.get("/households/{household_id}/merchant_aliases", response_model=List[schemas.MerchantAliasRead])
def list_merchant_aliases(household_id: int, request: Request, db: Session = Depends(get_db)):
    ensure_household_exists(db, household_id, request)
    return db.query(models.MerchantAlias).filter_by(household_id=household_id).all()


@app.post("/households/{household_id}/merchant_aliases", response_model=schemas.MerchantAliasRead, status_code=status.HTTP_201_CREATED)
def create_merchant_alias(household_id: int, alias: schemas.MerchantAliasCreate, request: Request, db: Session = Depends(get_db)):
    ensure_household_exists(db, household_id, request)
    db_alias = models.MerchantAlias(household_id=household_id, alias=alias.alias.strip().lower(), canonical_name=alias.canonical_name.strip(), category_hint=alias.category_hint)
    db.add(db_alias)
    db.commit()
    db.refresh(db_alias)
    return db_alias


@app.delete("/households/{household_id}/merchant_aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_merchant_alias(household_id: int, alias_id: int, request: Request, db: Session = Depends(get_db)):
    ensure_household_exists(db, household_id, request)
    alias = db.get(models.MerchantAlias, alias_id)
    if alias is None or alias.household_id != household_id:
        raise HTTPException(status_code=404, detail="Alias hittades inte.")
    db.delete(alias)
    db.commit()
    return


@app.get("/housing_scenarios/{scenario_id}/evaluate", response_model=schemas.HousingScenarioEvaluationRead)
def evaluate_housing_scenario_endpoint(scenario_id: int, db: Session = Depends(get_db)):
    scenario = get_object_or_404(db, models.HousingScenario, scenario_id)
    return calculations.evaluate_housing_scenario(scenario)


@app.post("/households/{household_id}/assistant/import_files", response_model=schemas.AssistantPromptResponse)
def import_files_endpoint(
    household_id: int,
    request: Request,
    files: List[UploadFile] = File(...),
    prompt: str | None = Form(None),
    db: Session = Depends(get_db)
):
    ensure_household_exists(db, household_id, request)
    thread = _get_active_chat_thread(db, household_id)
    staged_documents: list[models.Document] = []

    for upload in files:
        storage_path, checksum, raw = upload_to_disk(household_id, upload)
        extracted = extract_text_from_upload(raw, file_name=upload.filename, mime_type=upload.content_type)
        extraction_status, processing_error = _status_for_uploaded_document(extracted.text, extracted.extraction_mode)
        document = models.Document(
            household_id=household_id,
            document_type="receipt",
            file_name=upload.filename or "uploaded-file",
            mime_type=upload.content_type,
            checksum=checksum,
            extracted_text=extracted.text,
            extraction_status=extraction_status,
            processing_error=processing_error,
            storage_path=storage_path,
        )
        db.add(document)
        db.flush()
        staged_documents.append(document)

    db.commit()

    answer_lines = [
        "Jag lade filerna i **Dokument** för riktig tolkning och granskning.",
        "Assistentchatten skriver inte filer direkt till ekonomin och simulerar inte längre import här.",
    ]
    if prompt and prompt.strip():
        answer_lines.append("Din fråga sparades inte mot filerna ännu. Kör granskning/apply i Dokument först och fråga sedan assistenten.")
    answer_lines.append("")
    for document in staged_documents:
        status_label = _status_label_sv(document.extraction_status)
        note = "Text kunde extraheras." if document.extracted_text else (document.processing_error or "Ingen text kunde extraheras ännu.")
        answer_lines.append(f"- {document.file_name}: {status_label}. {note}")
    answer_lines.append("")
    answer_lines.append("Nästa steg: öppna **Dokument**, analysera underlaget och skapa reviewutkast därifrån.")

    file_names = [document.file_name for document in staged_documents]
    document_ids = [document.id for document in staged_documents]
    prompt_text = prompt or f"Laddade upp {len(staged_documents)} filer i assistenten."
    _append_chat_message(
        db,
        household_id,
        "user",
        prompt_text,
        message_type="user_upload",
        content_json={
            "file_names": file_names,
            "document_ids": document_ids,
        },
        thread=thread,
    )
    _append_chat_message(
        db,
        household_id,
        "system",
        "\n".join(answer_lines),
        message_type="system_import_notice",
        content_json={
            "document_ids": document_ids,
            "file_names": file_names,
            "provider": "system",
            "model": "document-staging-v1",
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        },
        thread=thread,
    )

    return {
        "household_id": household_id,
        "prompt": prompt or f"Laddade upp {len(files)} filer.",
        "answer": "\n".join(answer_lines),
        "provider": "system",
        "model": "document-staging-v1",
        "usage": schemas.AIUsageRead(input_tokens=0, output_tokens=0, total_tokens=0),
    }

def _get_active_chat_thread(db: Session, household_id: int) -> models.ChatThread:
    thread = db.query(models.ChatThread).filter_by(household_id=household_id, is_active=True).first()
    if not thread:
        thread = models.ChatThread(household_id=household_id, label="General Discussion")
        db.add(thread)
        db.commit()
        db.refresh(thread)
    return thread


def _append_chat_message(
    db: Session,
    household_id: int,
    role: str,
    content_text: str,
    *,
    message_type: str,
    content_json: dict[str, Any] | None = None,
    thread: models.ChatThread | None = None,
) -> models.ChatMessage:
    thread = thread or _get_active_chat_thread(db, household_id)
    thread.updated_at = datetime.utcnow()
    message = models.ChatMessage(
        thread_id=thread.id,
        role=role,
        message_type=message_type,
        content_text=content_text,
        content_json=content_json,
    )
    db.add(thread)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def _assistant_conversation_from_thread(
    db: Session,
    thread_id: int,
    *,
    exclude_message_id: int | None = None,
    limit: int = 10,
) -> list[schemas.AssistantMessageRead]:
    query = db.query(models.ChatMessage).filter(models.ChatMessage.thread_id == thread_id)
    if exclude_message_id is not None:
        query = query.filter(models.ChatMessage.id != exclude_message_id)
    messages = query.order_by(models.ChatMessage.id.asc()).all()[-limit:]
    conversation: list[schemas.AssistantMessageRead] = []
    for message in messages:
        if message.role not in {"user", "assistant"}:
            continue
        compact_content = (message.content_text or "").strip()
        if len(compact_content) > 500:
            compact_content = f"{compact_content[:500]}..."
        conversation.append(schemas.AssistantMessageRead(role=message.role, content=compact_content))
    return conversation


def _find_pending_applyable_write_intent(
    db: Session,
    household_id: int,
    thread_id: int,
) -> models.ChatMessage | None:
    assistant_messages = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.thread_id == thread_id,
            models.ChatMessage.role == "assistant",
            models.ChatMessage.message_type == "assistant_response",
        )
        .order_by(models.ChatMessage.id.desc())
        .all()
    )
    for candidate in assistant_messages:
        write_intent = (candidate.content_json or {}).get("write_intent") or {}
        if not write_intent or write_intent.get("intent") in {None, "none"}:
            continue
        if write_intent.get("missing_fields"):
            continue
        already_applied = (
            db.query(models.ChatMessage.id)
            .filter(
                models.ChatMessage.thread_id == thread_id,
                models.ChatMessage.role == "system",
                models.ChatMessage.message_type == "system_confirmation",
                models.ChatMessage.content_json["source_message_id"].as_integer() == candidate.id,
            )
            .first()
        )
        if already_applied:
            continue
        return candidate
    return None


def _is_apply_confirmation_prompt(prompt: str) -> bool:
    lowered = (prompt or "").strip().lower()
    if not lowered:
        return False
    confirmation_phrases = (
        "skriv in",
        "spara nu",
        "godkänn nu",
        "kör på",
        "ja, skriv",
        "ja skriv",
        "lägg in nu",
    )
    return any(phrase in lowered for phrase in confirmation_phrases)

@app.get("/households/{household_id}/assistant/thread", response_model=schemas.ChatThreadRead)
def get_active_thread(
    household_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)
    thread = _get_active_chat_thread(db, household_id)
    db.refresh(thread)
    return thread

@app.post("/households/{household_id}/assistant/thread/reset")
def reset_active_thread(
    household_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)
    old_thread = db.query(models.ChatThread).filter_by(household_id=household_id, is_active=True).first()
    if old_thread:
        old_thread.is_active = False
        db.add(old_thread)
        db.commit()
    return {"status": "ok"}


@app.post(
    "/households/{household_id}/assistant/respond",
    response_model=schemas.AssistantPromptResponse,
)
def household_assistant_respond(
    household_id: int,
    request: Request,
    request_body: schemas.AssistantPromptRequest,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)

    thread = _get_active_chat_thread(db, household_id)

    user_message = _append_chat_message(
        db,
        household_id,
        "user",
        request_body.prompt,
        message_type="user_prompt",
        thread=thread,
    )

    handled_by_import, import_answer, import_model = import_services.maybe_handle_assistant_prompt(
        db,
        household_id,
        request_body.prompt,
    )
    if handled_by_import:
        _append_chat_message(
            db,
            household_id,
            "system",
            import_answer,
            message_type="system_import_notice",
            content_json={
                "provider": "system",
                "model": import_model,
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            },
            thread=thread,
        )
        return {
            "household_id": household_id,
            "prompt": request_body.prompt,
            "answer": import_answer,
            "provider": "system",
            "model": import_model,
            "usage": schemas.AIUsageRead(input_tokens=0, output_tokens=0, total_tokens=0),
        }

    pending_intent_message = None
    if _is_apply_confirmation_prompt(request_body.prompt):
        pending_intent_message = _find_pending_applyable_write_intent(db, household_id, thread.id)
    if pending_intent_message is not None:
        pending_response_json = {"provider": "system", "model": "assistant-apply-guard"}
        reminder = "Jag har förberett ändringen. Tryck Godkänn och spara för att skriva den till systemet."
        _append_chat_message(
            db,
            household_id,
            "assistant",
            reminder,
            message_type="assistant_response",
            content_json=pending_response_json,
            thread=thread,
        )
        return {
            "household_id": household_id,
            "prompt": request_body.prompt,
            "answer": reminder,
            "questions": [],
            "write_intent": None,
            "provider": "system",
            "model": "assistant-apply-guard",
            "usage": None,
        }

    try:
        answer, questions, write_intent, model_name, usage = ai_services.generate_analysis_answer(
            db,
            household_id,
            request_body.prompt,
            _assistant_conversation_from_thread(db, thread.id, exclude_message_id=user_message.id),
            settings,
        )
    except ai_services.AIProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ai_services.AIProviderResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_public_ai_error_detail(exc, surface="assistant"),
        ) from exc

    response_json = {}
    if questions:
        response_json["questions"] = questions
    if write_intent:
        response_json["write_intent"] = write_intent.dict()
    response_json["provider"] = "openai"
    response_json["model"] = model_name
    if usage:
        response_json["usage"] = usage.dict(exclude_none=True)

    _append_chat_message(
        db,
        household_id,
        "assistant",
        answer,
        message_type="assistant_response",
        content_json=response_json if response_json else None,
        thread=thread,
    )

    return {
        "household_id": household_id,
        "prompt": request_body.prompt,
        "answer": answer,
        "questions": questions,
        "write_intent": write_intent.dict() if write_intent else None,
        "provider": "openai",
        "model": model_name,
        "usage": usage,
    }

@app.post("/households/{household_id}/assistant/apply_intent")
def household_assistant_apply_intent(
    household_id: int,
    request: Request,
    request_body: schemas.AssistantIntentApplyRequest,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)
    resolved_intent, resolved_target, resolved_data = _resolve_apply_request_from_source(
        db,
        household_id,
        request_body,
    )

    if resolved_intent == "create_expense":
        return _process_create_expense(db, household_id, resolved_data, request_body.source_message_id, resolved_intent)
    elif resolved_intent == "create_planned_purchase":
        return _process_create_planned_purchase(db, household_id, resolved_data, request_body.source_message_id, resolved_intent)
    elif resolved_intent == "create_income":
        return _process_create_income(db, household_id, resolved_data, request_body.source_message_id, resolved_intent)
    elif resolved_intent == "create_subscription":
        return _process_create_subscription(db, household_id, resolved_data, request_body.source_message_id, resolved_intent)
    elif resolved_intent == "delete_entity":
        return _process_delete_entity(db, household_id, resolved_data, request_body.source_message_id, resolved_intent)
    elif resolved_intent == "update_entity":
        return _process_update_entity(db, household_id, resolved_data, request_body.source_message_id, resolved_intent)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Okänt intent: {resolved_intent}")


def _normalize_assistant_apply_data(request_body: schemas.AssistantIntentApplyRequest) -> dict[str, Any]:
    data = dict(request_body.data or {})
    if request_body.intent == "update_entity":
        entity_type = request_body.target_entity_type or data.get("entity_type") or data.get("target_entity_type")
        entity_id = data.get("entity_id", data.get("id"))
        updates = data.get("updates")
        proposed_updates = data.get("proposed_updates")
        if updates is None and isinstance(proposed_updates, list) and len(proposed_updates) == 1 and isinstance(proposed_updates[0], dict):
            proposed = proposed_updates[0]
            entity_type = entity_type or proposed.get("entity_type")
            entity_id = entity_id or proposed.get("entity_id") or proposed.get("id")
            updates = proposed.get("updates")
        if updates is None:
            updates = {
                key: value
                for key, value in data.items()
                if key not in {"id", "entity_id", "entity_type", "target_entity_type", "match", "proposed_updates", "previous_values", "summary", "description", "label"}
            }
        if entity_type == "recurring_cost" and isinstance(updates, dict) and "monthly_amount" in updates and "amount" not in updates:
            updates["amount"] = updates.pop("monthly_amount")
        if entity_type == "loan" and isinstance(updates, dict) and "monthly_payment" in updates and "required_monthly_payment" not in updates:
            updates["required_monthly_payment"] = updates.pop("monthly_payment")
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "match": data.get("match"),
            "updates": updates,
            "previous_values": data.get("previous_values", {}),
        }
    if request_body.intent == "delete_entity":
        return {
            "entity_type": request_body.target_entity_type or data.get("entity_type"),
            "entity_id": data.get("entity_id", data.get("id")),
        }
    return data


def _resolve_apply_request_from_source(
    db: Session,
    household_id: int,
    request_body: schemas.AssistantIntentApplyRequest,
) -> tuple[str, str | None, dict[str, Any]]:
    source_message = _validate_source_message_for_apply(db, household_id, request_body.source_message_id)
    stored_intent_raw = (source_message.content_json or {}).get("write_intent") or {}
    stored_intent = str(stored_intent_raw.get("intent") or "").strip()
    if not stored_intent:
        raise HTTPException(status_code=409, detail="Källmeddelandet saknar giltigt write_intent.")
    stored_target = stored_intent_raw.get("target_entity_type")
    stored_data = _normalize_assistant_apply_data(
        schemas.AssistantIntentApplyRequest(
            intent=stored_intent,
            target_entity_type=stored_target,
            data=stored_intent_raw.get("data") or {},
            source_message_id=request_body.source_message_id,
        )
    )
    proposed_updates = stored_intent_raw.get("data", {}).get("proposed_updates")
    if isinstance(proposed_updates, list) and len(proposed_updates) > 1:
        raise HTTPException(status_code=409, detail="Batch-apply stöds inte för flera föreslagna uppdateringar i samma intent.")

    # Optional client payload is allowed only as audit/mismatch safety check.
    if request_body.intent or request_body.target_entity_type or request_body.data is not None:
        requested_intent = request_body.intent or stored_intent
        if requested_intent != stored_intent:
            raise HTTPException(status_code=409, detail="Apply-intent matchar inte intent i källmeddelandet.")
        requested_target = request_body.target_entity_type or stored_target or stored_data.get("entity_type")
        if stored_target and requested_target and stored_target != requested_target:
            raise HTTPException(status_code=409, detail="Apply-intent matchar inte målentiteten i källmeddelandet.")
        requested_data = _normalize_assistant_apply_data(
            schemas.AssistantIntentApplyRequest(
                intent=stored_intent,
                target_entity_type=requested_target,
                data=request_body.data or {},
                source_message_id=request_body.source_message_id,
            )
        )
        if _normalize_intent_data_for_compare(stored_intent, stored_data) != _normalize_intent_data_for_compare(stored_intent, requested_data):
            raise HTTPException(status_code=409, detail="Apply-intentens data har ändrats efter assistantsvaret.")

    if stored_intent == "update_entity":
        stored_data = _resolve_update_entity_reference(db, household_id, stored_data, stored_target)

    return stored_intent, stored_target, stored_data


def _normalize_housing_category(category: str | None) -> str | None:
    if category is None:
        return None
    normalized = str(category).strip().lower()
    if normalized == "housing":
        return "boende"
    return normalized or None


def _resolve_update_entity_reference(
    db: Session,
    household_id: int,
    data: dict[str, Any],
    fallback_target_entity_type: str | None,
) -> dict[str, Any]:
    entity_type = (data.get("entity_type") or fallback_target_entity_type or "").strip()
    entity_id = data.get("entity_id")
    updates = data.get("updates")
    match = data.get("match") if isinstance(data.get("match"), dict) else {}
    if not entity_type:
        raise HTTPException(status_code=400, detail="Update-intent saknar entity_type.")
    if not isinstance(updates, dict) or not updates:
        raise HTTPException(status_code=400, detail="Update-intent saknar updates.")

    if entity_id is None and match:
        entity_id = match.get("entity_id") or match.get("id")
    if entity_id is not None:
        return {"entity_type": entity_type, "entity_id": int(entity_id), "updates": updates}

    model_class = _get_model_class_for_entity(entity_type)
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Ogiltig entity_type för uppdatering: {entity_type}")

    if entity_type == "recurring_cost":
        query = db.query(models.RecurringCost).filter(models.RecurringCost.household_id == household_id)
        category = _normalize_housing_category(match.get("category"))
        if category:
            query = query.filter(models.RecurringCost.category.ilike(category))
        vendor = match.get("vendor")
        if vendor:
            query = query.filter(models.RecurringCost.vendor.ilike(str(vendor)))
        status = match.get("status")
        if status:
            query = query.filter(models.RecurringCost.status == status)
        candidates = query.order_by(models.RecurringCost.id.asc()).all()
    elif entity_type == "loan":
        query = db.query(models.Loan).filter(models.Loan.household_id == household_id)
        lender = match.get("lender")
        if lender:
            query = query.filter(models.Loan.lender.ilike(str(lender)))
        purpose = match.get("purpose")
        if purpose:
            query = query.filter(models.Loan.purpose.ilike(str(purpose)))
        status = match.get("status")
        if status:
            query = query.filter(models.Loan.status == status)
        candidates = query.order_by(models.Loan.id.asc()).all()
    elif entity_type == "subscription_contract":
        query = db.query(models.SubscriptionContract).filter(models.SubscriptionContract.household_id == household_id)
        provider = match.get("provider")
        if provider:
            query = query.filter(models.SubscriptionContract.provider.ilike(str(provider)))
        category = match.get("category")
        if category:
            query = query.filter(models.SubscriptionContract.category == category)
        status = match.get("status")
        if status:
            query = query.filter(models.SubscriptionContract.status == status)
        candidates = query.order_by(models.SubscriptionContract.id.asc()).all()
    else:
        raise HTTPException(status_code=400, detail="Update-intent kräver entity_id för denna entity_type.")

    if len(candidates) == 0:
        raise HTTPException(status_code=409, detail="Update-intent kunde inte matcha någon entitet för apply.")
    if len(candidates) > 1:
        raise HTTPException(status_code=409, detail="Update-intent matchar flera entiteter. Specificera exakt post innan apply.")
    return {"entity_type": entity_type, "entity_id": int(candidates[0].id), "updates": updates}


def _validate_source_message_for_apply(
    db: Session,
    household_id: int,
    source_message_id: int | None,
) -> models.ChatMessage:
    if source_message_id is None:
        raise HTTPException(
            status_code=400,
            detail="Apply kräver source_message_id från ett sparat assistantsvar.",
        )
    source_message = (
        db.query(models.ChatMessage)
        .join(models.ChatThread, models.ChatMessage.thread_id == models.ChatThread.id)
        .filter(
            models.ChatMessage.id == source_message_id,
            models.ChatMessage.role == "assistant",
            models.ChatMessage.message_type == "assistant_response",
            models.ChatThread.household_id == household_id,
        )
        .first()
    )
    if source_message is None:
        raise HTTPException(status_code=404, detail="Kunde inte hitta källmeddelandet för apply.")
    stored_intent = (source_message.content_json or {}).get("write_intent")
    if not stored_intent:
        raise HTTPException(status_code=409, detail="Källmeddelandet saknar sparat write_intent.")
    if stored_intent.get("missing_fields"):
        raise HTTPException(status_code=409, detail="Write-intent saknar fortfarande obligatoriska fält.")
    already_applied = (
        db.query(models.ChatMessage.id)
        .filter(
            models.ChatMessage.thread_id == source_message.thread_id,
            models.ChatMessage.role == "system",
            models.ChatMessage.message_type == "system_confirmation",
            models.ChatMessage.content_json["source_message_id"].as_integer() == source_message_id,
        )
        .first()
    )
    if already_applied:
        raise HTTPException(status_code=409, detail="Write-intent har redan applicerats.")
    return source_message


def _validate_apply_intent_against_source_message(
    db: Session,
    household_id: int,
    request_body: schemas.AssistantIntentApplyRequest,
    normalized_data: dict[str, Any],
) -> None:
    # Legacy helper retained for compatibility with older tests/imports.
    _resolve_apply_request_from_source(db, household_id, request_body)


def _normalize_intent_data_for_compare(intent: str, data: dict[str, Any]) -> dict[str, Any]:
    if intent == "update_entity":
        updates = dict(data.get("updates") or {})
        return {
            "entity_type": data.get("entity_type"),
            "entity_id": data.get("entity_id") or data.get("id"),
            "match": data.get("match") if isinstance(data.get("match"), dict) else None,
            "updates": updates,
        }
    if intent == "delete_entity":
        return {
            "entity_type": data.get("entity_type"),
            "entity_id": data.get("entity_id") or data.get("id"),
        }
    return dict(data)


def _get_model_class_for_entity(entity_type: str):
    return {
        "income_source": models.IncomeSource,
        "loan": models.Loan,
        "recurring_cost": models.RecurringCost,
        "subscription_contract": models.SubscriptionContract,
        "planned_purchase": models.PlannedPurchase,
        "insurance_policy": models.InsurancePolicy,
        "vehicle": models.Vehicle,
        "asset": models.Asset,
        "housing_scenario": models.HousingScenario,
        "scenario": models.Scenario,
        "report_snapshot": models.ReportSnapshot,
        "person": models.Person,
    }.get(entity_type)


def _has_value(data: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return True
    return False


def _require_assistant_fields(data: dict[str, Any], fields: list[tuple[str, ...]], *, intent: str) -> None:
    missing = ["/".join(keys) for keys in fields if not _has_value(data, *keys)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Write-intent {intent} saknar obligatoriska fält: {', '.join(missing)}.",
        )

def _save_system_confirmation(
    db: Session,
    household_id: int,
    message: str,
    *,
    source_message_id: int | None = None,
    intent: str | None = None,
    result: dict[str, Any] | None = None,
):
    content_json: dict[str, Any] = {"applied": True}
    if source_message_id is not None:
        content_json["source_message_id"] = source_message_id
    if intent:
        content_json["intent"] = intent
    if result:
        content_json["result"] = result
    _append_chat_message(
        db,
        household_id,
        "system",
        message,
        message_type="system_confirmation",
        content_json=content_json,
    )


def _first_person_id_for_household(db: Session, household_id: int) -> int:
    person = db.query(models.Person).filter_by(household_id=household_id).order_by(models.Person.id.asc()).first()
    if person is None:
        raise HTTPException(status_code=400, detail="Hushållet saknar person att koppla inkomsten till.")
    return int(person.id)


def _validated_create_expense_payload(household_id: int, data: dict[str, Any]) -> schemas.RecurringCostCreate:
    _require_assistant_fields(data, [("category",), ("amount",), ("frequency",)], intent="create_expense")
    payload = {
        "household_id": household_id,
        "person_id": data.get("person_id"),
        "category": data.get("category") or "other",
        "subcategory": data.get("subcategory"),
        "amount": float(data.get("amount", 0) or 0.0),
        "frequency": data.get("frequency") or "monthly",
        "mandatory": data.get("mandatory", True),
        "variability_class": data.get("variability_class") or "fixed",
        "controllability": data.get("controllability") or "locked",
        "vendor": data.get("vendor"),
        "payment_method": data.get("payment_method"),
        "due_day": data.get("due_day"),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "status": data.get("status") or "active",
        "note": data.get("note"),
    }
    return schemas.RecurringCostCreate(**payload)


def _validated_create_income_payload(db: Session, household_id: int, data: dict[str, Any]) -> schemas.IncomeSourceCreate:
    _require_assistant_fields(data, [("person_id",), ("amount", "net_amount", "gross_amount"), ("frequency",)], intent="create_income")
    person_id = data.get("person_id")
    person = db.get(models.Person, person_id)
    if person is None or person.household_id != household_id:
        raise HTTPException(status_code=400, detail="Ogiltig person för income_source.")
    payload = {
        "person_id": person_id,
        "type": data.get("type") or "salary",
        "gross_amount": data.get("gross_amount"),
        "net_amount": float(data.get("amount", data.get("net_amount", 0)) or 0.0),
        "frequency": data.get("frequency") or "monthly",
        "regularity": data.get("regularity") or "fixed",
        "source": data.get("source") or "Inkomst",
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "verified": data.get("verified", False),
        "verification_doc_id": data.get("verification_doc_id"),
        "note": data.get("note"),
    }
    return schemas.IncomeSourceCreate(**payload)


def _validated_create_subscription_payload(household_id: int, data: dict[str, Any]) -> schemas.SubscriptionContractCreate:
    _require_assistant_fields(
        data,
        [("provider",), ("amount", "current_monthly_cost"), ("frequency", "billing_frequency")],
        intent="create_subscription",
    )
    payload = {
        "household_id": household_id,
        "person_id": data.get("person_id"),
        "category": data.get("category") or "other",
        "provider": data.get("provider") or "Abonnemang",
        "product_name": data.get("product_name"),
        "contract_type": data.get("contract_type") or "subscription",
        "current_monthly_cost": float(data.get("amount", data.get("current_monthly_cost", 0)) or 0.0),
        "promotional_cost": data.get("promotional_cost"),
        "promotional_end_date": data.get("promotional_end_date"),
        "ordinary_cost": data.get("ordinary_cost"),
        "billing_frequency": data.get("frequency", data.get("billing_frequency")) or "monthly",
        "binding_start_date": data.get("binding_start_date"),
        "binding_end_date": data.get("binding_end_date"),
        "notice_period_days": data.get("notice_period_days"),
        "auto_renew": data.get("auto_renew", True),
        "cancellation_method": data.get("cancellation_method"),
        "cancellation_url": data.get("cancellation_url"),
        "service_address": data.get("service_address"),
        "usage_metric_type": data.get("usage_metric_type"),
        "usage_metric_estimate": data.get("usage_metric_estimate"),
        "included_allowance": data.get("included_allowance"),
        "overage_risk": data.get("overage_risk"),
        "bundling_flag": data.get("bundling_flag", False),
        "household_criticality": data.get("household_criticality", "optional"),
        "market_checkable": data.get("market_checkable", True),
        "last_negotiated_at": data.get("last_negotiated_at"),
        "next_review_at": data.get("next_review_at"),
        "latest_invoice_doc_id": data.get("latest_invoice_doc_id"),
        "status": data.get("status") or "active",
        "note": data.get("note"),
    }
    return schemas.SubscriptionContractCreate(**payload)


def _validated_create_planned_purchase_payload(data: dict[str, Any]) -> analysis_schemas.PlannedPurchaseItem:
    _require_assistant_fields(data, [("title", "description"), ("amount", "estimated_amount")], intent="create_planned_purchase")
    payload = {
        "id": data.get("id"),
        "title": data.get("title") or data.get("description") or "Nytt köp",
        "category": data.get("category"),
        "estimated_amount": float(data.get("amount", data.get("estimated_amount", 0)) or 0.0),
        "priority": data.get("priority") or "optional",
        "due_window": data.get("due_window"),
        "status": data.get("status") or "planned",
    }
    return analysis_schemas.PlannedPurchaseItem(**payload)


def _load_entity_for_household(db: Session, model_class, entity_id: int, household_id: int):
    if model_class is models.IncomeSource:
        return (
            db.query(models.IncomeSource)
            .join(models.Person, models.IncomeSource.person_id == models.Person.id)
            .filter(models.IncomeSource.id == entity_id, models.Person.household_id == household_id)
            .first()
        )
    return (
        db.query(model_class)
        .filter(model_class.id == entity_id, model_class.household_id == household_id)
        .first()
    )


def _validated_update_payload(entity_type: str, obj, updates: dict[str, Any]) -> dict[str, Any]:
    if entity_type == "recurring_cost":
        payload = schemas.RecurringCostUpdate(**updates)
        return payload.dict(exclude_unset=True, exclude_none=True)
    if entity_type == "subscription_contract":
        payload = schemas.SubscriptionContractUpdate(**updates)
        return payload.dict(exclude_unset=True, exclude_none=True)
    if entity_type == "income_source":
        payload = schemas.IncomeSourceUpdate(**updates)
        return payload.dict(exclude_unset=True, exclude_none=True)
    if entity_type == "planned_purchase":
        allowed = {"title", "category", "estimated_amount", "amount", "priority", "due_window", "status", "note", "person_id"}
        normalized = {key: value for key, value in updates.items() if key in allowed}
        if "amount" in normalized and "estimated_amount" not in normalized:
            normalized["estimated_amount"] = normalized.pop("amount")
        return normalized
    allowed_keys = {key for key in updates.keys() if hasattr(obj, key)}
    return {key: updates[key] for key in allowed_keys}

def _process_create_expense(
    db: Session,
    household_id: int,
    data: dict[str, Any],
    source_message_id: int | None = None,
    intent: str | None = None,
):
    try:
        payload = _validated_create_expense_payload(household_id, data)
        cost = models.RecurringCost(**payload.dict(exclude_none=True))
        db.add(cost)
        db.commit()
        db.refresh(cost)

        _save_system_confirmation(
            db,
            household_id,
            f"Sparade ny utgift för **{cost.vendor or cost.category}** på **{cost.amount} kr** ({cost.frequency}).",
            source_message_id=source_message_id,
            intent=intent,
            result={"entity_type": "recurring_cost", "entity_id": cost.id},
        )

        return {"status": "success", "entity_type": "recurring_cost", "entity_id": cost.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def _process_create_income(
    db: Session,
    household_id: int,
    data: dict[str, Any],
    source_message_id: int | None = None,
    intent: str | None = None,
):
    try:
        payload = _validated_create_income_payload(db, household_id, data)
        inc = models.IncomeSource(**payload.dict(exclude_none=True))
        db.add(inc)
        db.commit()
        db.refresh(inc)

        _save_system_confirmation(
            db,
            household_id,
            f"Sparade ny inkomst från **{inc.source or 'Inkomst'}** på **{inc.net_amount or inc.gross_amount or 0} kr**.",
            source_message_id=source_message_id,
            intent=intent,
            result={"entity_type": "income_source", "entity_id": inc.id},
        )

        return {"status": "success", "entity_type": "income_source", "entity_id": inc.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def _process_create_subscription(
    db: Session,
    household_id: int,
    data: dict[str, Any],
    source_message_id: int | None = None,
    intent: str | None = None,
):
    try:
        payload = _validated_create_subscription_payload(household_id, data)
        sub = models.SubscriptionContract(**payload.dict(exclude_none=True))
        db.add(sub)
        db.commit()
        db.refresh(sub)

        _save_system_confirmation(
            db,
            household_id,
            f"Lade till abonnemang från **{sub.provider}** på **{sub.current_monthly_cost} kr**.",
            source_message_id=source_message_id,
            intent=intent,
            result={"entity_type": "subscription_contract", "entity_id": sub.id},
        )
        return {"status": "success", "entity_type": "subscription_contract", "entity_id": sub.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def _process_create_planned_purchase(
    db: Session,
    household_id: int,
    data: dict[str, Any],
    source_message_id: int | None = None,
    intent: str | None = None,
):
    try:
        payload = _validated_create_planned_purchase_payload(data)
        purch = models.PlannedPurchase(
            household_id=household_id,
            title=payload.title,
            category=payload.category,
            estimated_amount=payload.estimated_amount,
            priority=payload.priority,
            due_window=payload.due_window,
            status=payload.status,
        )
        db.add(purch)
        db.commit()
        db.refresh(purch)
        _save_system_confirmation(
            db,
            household_id,
            f"Sparade ett planerat köp: **{purch.title}** ({purch.estimated_amount} kr).",
            source_message_id=source_message_id,
            intent=intent,
            result={"entity_type": "planned_purchase", "entity_id": purch.id},
        )
        return {"status": "success", "entity_type": "planned_purchase", "entity_id": purch.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def _process_update_entity(
    db: Session,
    household_id: int,
    data: dict[str, Any],
    source_message_id: int | None = None,
    intent: str | None = None,
):
    entity_type = data.get("entity_type")
    entity_id = data.get("entity_id")
    updates = data.get("updates", {})
    if not entity_type or not entity_id or not updates:
        raise HTTPException(status_code=400, detail="Saknar entity_type, entity_id eller updates för update_entity")

    model_class = _get_model_class_for_entity(entity_type)
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Ogiltig entity_type för uppdatering: {entity_type}")

    obj = _load_entity_for_household(db, model_class, entity_id, household_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Kunde inte hitta objektet som skulle uppdateras")

    validated_updates = _validated_update_payload(entity_type, obj, updates)
    updated_fields = []
    for k, v in validated_updates.items():
        if k in {"id", "household_id"}:
            continue
        if hasattr(obj, k):
            setattr(obj, k, v)
            updated_fields.append(f"{k} -> {v}")

    db.add(obj)
    db.commit()

    _save_system_confirmation(
        db,
        household_id,
        f"Uppdaterade **{entity_type}** (ID {entity_id}). Fält i ändring: {', '.join(updated_fields)}",
        source_message_id=source_message_id,
        intent=intent,
        result={"entity_type": entity_type, "entity_id": entity_id},
    )
    return {"status": "success", "entity_type": entity_type, "entity_id": entity_id}

def _process_delete_entity(
    db: Session,
    household_id: int,
    data: dict[str, Any],
    source_message_id: int | None = None,
    intent: str | None = None,
):
    entity_type = data.get("entity_type")
    entity_id = data.get("entity_id")
    if not entity_type or not entity_id:
        raise HTTPException(status_code=400, detail="Saknar entity_type eller entity_id för delete_entity")

    model_class = _get_model_class_for_entity(entity_type)
    if not model_class:
        raise HTTPException(status_code=400, detail=f"Ogiltig entity_type för radering: {entity_type}")

    obj = _load_entity_for_household(db, model_class, entity_id, household_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Kunde inte hitta objektet som skulle raderas")

    if entity_type == "planned_purchase":
        db.delete(obj)
    elif hasattr(obj, "status"):
        obj.status = "ended" if entity_type != "loan" else "closed"
        db.add(obj)
    elif hasattr(obj, "active"):
        obj.active = False
        db.add(obj)
    else:
        db.delete(obj)

    db.commit()
    _save_system_confirmation(
        db,
        household_id,
        f"Tog bort/avslutade **{entity_type}** (ID {entity_id}).",
        source_message_id=source_message_id,
        intent=intent,
        result={"entity_type": entity_type, "entity_id": entity_id},
    )
    return {"status": "success", "entity_type": entity_type, "entity_id": entity_id}


@app.post(
    "/households/{household_id}/ingest_ai/analyze",
    response_model=schemas.IngestAnalyzeResponse,
)
def household_ingest_ai_analyze(
    household_id: int,
    request: Request,
    request_body: schemas.IngestAnalyzeRequest,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)
    try:
        response, _ = ai_services.analyze_ingest_input(
            db,
            household_id,
            input_text=request_body.input_text,
            input_kind=request_body.input_kind or "unknown",
            source_channel=request_body.source_channel,
            document_id=request_body.document_id,
            source_name=request_body.source_name,
            settings=settings,
        )
        return response
    except ai_services.AIProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ai_services.AIInputNotSupportedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    except ai_services.AIProviderResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_public_ai_error_detail(exc, surface="ingest"),
        ) from exc


@app.post(
    "/households/{household_id}/ingest_ai/promote",
    response_model=schemas.IngestPromoteResponse,
)
def household_ingest_ai_promote(
    household_id: int,
    request: Request,
    request_body: schemas.IngestPromoteRequest,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)
    try:
        return ai_services.promote_ingest_suggestions(db, household_id, request_body)
    except ai_services.AIInputNotSupportedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    except ai_services.AIProviderResponseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc



@app.get("/households/{household_id}/analysis")
def get_household_analysis(
    household_id: int,
    request: Request,
    current_balance: Optional[float] = None,
    as_of: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Full deterministic analysis of household economics.

    No LLM calls. Same input → same output.
    Returns: historical, cycle, planned, subscriptions, forecast, actions.
    """
    ensure_household_exists(db, household_id, request)
    return build_analysis_output(db, household_id, current_balance, as_of=as_of)


@app.get("/households/{household_id}/analysis/cycle")
def get_cycle_status(
    household_id: int,
    request: Request,
    current_balance: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """Current payday cycle status. Deterministic."""
    ensure_household_exists(db, household_id, request)
    records = calculations.load_household_records(db, household_id)
    return compute_cycle_status(records, current_balance=current_balance).dict()


# --- Planned Purchase CRUD ---

@app.get("/households/{household_id}/planned_purchases")
def list_planned_purchases(
    household_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)
    items = db.query(models.PlannedPurchase).filter_by(household_id=household_id).order_by(models.PlannedPurchase.id).all()
    return [calculations.serialize_model(item) for item in items]


@app.post("/households/{household_id}/planned_purchases", status_code=status.HTTP_201_CREATED)
def create_planned_purchase(
    household_id: int,
    request: Request,
    body: analysis_schemas.PlannedPurchaseItem,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)
    item = models.PlannedPurchase(
        household_id=household_id,
        title=body.title,
        category=body.category,
        estimated_amount=body.estimated_amount,
        priority=body.priority,
        due_window=body.due_window,
        status=body.status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return calculations.serialize_model(item)


@app.put("/households/{household_id}/planned_purchases/{purchase_id}")
def update_planned_purchase(
    household_id: int,
    purchase_id: int,
    request: Request,
    body: analysis_schemas.PlannedPurchaseItem,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)
    item = db.query(models.PlannedPurchase).filter_by(id=purchase_id, household_id=household_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Köp hittades inte.")
    item.title = body.title
    item.category = body.category
    item.estimated_amount = body.estimated_amount
    item.priority = body.priority
    item.due_window = body.due_window
    item.status = body.status
    db.commit()
    db.refresh(item)
    return calculations.serialize_model(item)


@app.delete("/households/{household_id}/planned_purchases/{purchase_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_planned_purchase(
    household_id: int,
    purchase_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ensure_household_exists(db, household_id, request)
    item = db.query(models.PlannedPurchase).filter_by(id=purchase_id, household_id=household_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Köp hittades inte.")
    db.delete(item)
    db.commit()
    return


@app.get("/{frontend_path:path}", include_in_schema=False)
def frontend_app(frontend_path: str):
    if frontend_path.startswith("assets/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return FileResponse(STATIC_ROOT / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)
