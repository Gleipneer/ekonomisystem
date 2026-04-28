"""
Pydantic schemas used for validation and serialization of API payloads.

Each SQLAlchemy model defined in ``models.py`` has a corresponding pair
of Pydantic models: one for incoming data (``Create`` / ``Update``) and
one for outgoing data (``Read``). Create/Update models omit primary key
fields so that clients cannot set them. Read models include all columns
and enable ``orm_mode`` so that they can be constructed directly from
SQLAlchemy ORM objects.

Complex nested relationships are not included in the default schemas to
avoid deep recursion and large payloads. Endpoints can provide richer
responses by composing nested schemas explicitly.
"""

from datetime import date, datetime
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, Field, confloat, root_validator

from .models import IncomeFrequency, LoanRepaymentModel, VariabilityClass, Controllability, SubscriptionCategory


# -------- Auth & Users --------
class AppUserBase(BaseModel):
    username: str
    household_id: Optional[int] = None

class AppUserCreate(BaseModel):
    username: str
    password: str
    household_name: Optional[str] = None

class AppUserRead(AppUserBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

# -------- ImportSession --------
class UnresolvedQuestionBase(BaseModel):
    import_session_id: int
    kind: str
    question_text: str
    related_refs: Optional[Any] = None
    confidence: Optional[float] = None
    answer: Optional[str] = None
    status: Optional[str] = Field(default="pending")

class UnresolvedQuestionRead(UnresolvedQuestionBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

class ImportSessionBase(BaseModel):
    household_id: int
    label: str
    status: Optional[str] = Field(default="active")

class ImportSessionRead(ImportSessionBase):
    id: int
    created_at: datetime
    unresolved_questions: List[UnresolvedQuestionRead] = Field(default_factory=list)
    class Config:
        orm_mode = True

# -------- Household --------
class HouseholdBase(BaseModel):
    name: str
    currency: Optional[str] = Field(default="SEK")
    primary_country: Optional[str] = Field(default="SE")


class HouseholdCreate(HouseholdBase):
    pass


class HouseholdUpdate(HouseholdBase):
    name: Optional[str] = None
    currency: Optional[str] = None
    primary_country: Optional[str] = None


class HouseholdRead(HouseholdBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

# -------- Chat --------
class ChatMessageCreate(BaseModel):
    role: str
    message_type: str = "message"
    content_text: str
    content_json: Optional[Any] = None

class ChatMessageRead(BaseModel):
    id: int
    thread_id: int
    role: str
    message_type: str
    content_text: str
    content_json: Optional[Any] = None
    created_at: datetime

    class Config:
        orm_mode = True

class ChatThreadRead(BaseModel):
    id: int
    household_id: int
    label: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    messages: List[ChatMessageRead] = Field(default_factory=list)

    class Config:
        orm_mode = True

# -------- Person --------
class PersonBase(BaseModel):
    household_id: int
    name: str
    role: Optional[str] = Field(default="self")
    income_share_mode: Optional[str] = Field(default="pooled")
    active: Optional[bool] = Field(default=True)


class PersonCreate(PersonBase):
    pass


class PersonUpdate(PersonBase):
    household_id: Optional[int] = None
    name: Optional[str] = None
    role: Optional[str] = None
    income_share_mode: Optional[str] = None
    active: Optional[bool] = None


class PersonRead(PersonBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# -------- IncomeSource --------
class IncomeSourceBase(BaseModel):
    person_id: int
    type: str
    gross_amount: Optional[float] = None
    net_amount: Optional[float] = None
    frequency: IncomeFrequency = IncomeFrequency.monthly
    regularity: Optional[str] = Field(default="fixed")
    source: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    verified: Optional[bool] = False
    verification_doc_id: Optional[int] = None
    note: Optional[str] = None


class IncomeSourceCreate(IncomeSourceBase):
    pass


class IncomeSourceUpdate(IncomeSourceBase):
    person_id: Optional[int] = None
    type: Optional[str] = None
    gross_amount: Optional[float] = None
    net_amount: Optional[float] = None
    frequency: Optional[IncomeFrequency] = None
    regularity: Optional[str] = None
    source: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    verified: Optional[bool] = None
    verification_doc_id: Optional[int] = None
    note: Optional[str] = None


class IncomeSourceRead(IncomeSourceBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# -------- Loan --------
class LoanBase(BaseModel):
    household_id: int
    person_id: Optional[int] = None
    type: str
    purpose: Optional[str] = None
    lender: Optional[str] = None
    original_amount: Optional[float] = None
    current_balance: Optional[float] = None
    remaining_term_months: Optional[int] = None
    planned_end_date: Optional[date] = None
    nominal_rate: Optional[float] = None
    effective_rate: Optional[float] = None
    repayment_model: LoanRepaymentModel = LoanRepaymentModel.annuity
    required_monthly_payment: Optional[float] = None
    amortization_amount_monthly: Optional[float] = None
    due_day: Optional[int] = None
    fixed_rate_until: Optional[date] = None
    secured: Optional[bool] = False
    linked_asset_id: Optional[int] = None
    autopay: Optional[bool] = False
    statement_doc_id: Optional[int] = None
    status: Optional[str] = Field(default="active")
    note: Optional[str] = None


class LoanCreate(LoanBase):
    pass


class LoanUpdate(LoanBase):
    household_id: Optional[int] = None
    person_id: Optional[int] = None
    type: Optional[str] = None
    purpose: Optional[str] = None
    lender: Optional[str] = None
    original_amount: Optional[float] = None
    current_balance: Optional[float] = None
    remaining_term_months: Optional[int] = None
    planned_end_date: Optional[date] = None
    nominal_rate: Optional[float] = None
    effective_rate: Optional[float] = None
    repayment_model: Optional[LoanRepaymentModel] = None
    required_monthly_payment: Optional[float] = None
    amortization_amount_monthly: Optional[float] = None
    due_day: Optional[int] = None
    fixed_rate_until: Optional[date] = None
    secured: Optional[bool] = None
    linked_asset_id: Optional[int] = None
    autopay: Optional[bool] = None
    statement_doc_id: Optional[int] = None
    status: Optional[str] = None
    note: Optional[str] = None


class LoanRead(LoanBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# -------- RecurringCost --------
class RecurringCostBase(BaseModel):
    household_id: int
    person_id: Optional[int] = None
    category: str
    subcategory: Optional[str] = None
    amount: float
    frequency: IncomeFrequency = IncomeFrequency.monthly
    mandatory: Optional[bool] = True
    variability_class: VariabilityClass = VariabilityClass.fixed
    controllability: Controllability = Controllability.locked
    vendor: Optional[str] = None
    payment_method: Optional[str] = None
    due_day: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(default="active")
    note: Optional[str] = None


class RecurringCostCreate(RecurringCostBase):
    pass


class RecurringCostUpdate(RecurringCostBase):
    household_id: Optional[int] = None
    person_id: Optional[int] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    amount: Optional[float] = None
    frequency: Optional[IncomeFrequency] = None
    mandatory: Optional[bool] = None
    variability_class: Optional[VariabilityClass] = None
    controllability: Optional[Controllability] = None
    vendor: Optional[str] = None
    payment_method: Optional[str] = None
    due_day: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    note: Optional[str] = None


class RecurringCostRead(RecurringCostBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# -------- SubscriptionContract --------
class SubscriptionContractBase(BaseModel):
    household_id: int
    person_id: Optional[int] = None
    category: SubscriptionCategory = SubscriptionCategory.other
    provider: str
    product_name: Optional[str] = None
    contract_type: Optional[str] = Field(default="subscription")
    current_monthly_cost: float
    promotional_cost: Optional[float] = None
    promotional_end_date: Optional[date] = None
    ordinary_cost: Optional[float] = None
    billing_frequency: IncomeFrequency = IncomeFrequency.monthly
    binding_start_date: Optional[date] = None
    binding_end_date: Optional[date] = None
    notice_period_days: Optional[int] = None
    auto_renew: Optional[bool] = True
    cancellation_method: Optional[str] = None
    cancellation_url: Optional[str] = None
    service_address: Optional[str] = None
    usage_metric_type: Optional[str] = None
    usage_metric_estimate: Optional[float] = None
    included_allowance: Optional[float] = None
    overage_risk: Optional[str] = None
    bundling_flag: Optional[bool] = False
    household_criticality: Optional[str] = Field(default="optional")
    market_checkable: Optional[bool] = True
    last_negotiated_at: Optional[date] = None
    next_review_at: Optional[date] = None
    latest_invoice_doc_id: Optional[int] = None
    status: Optional[str] = Field(default="active")
    note: Optional[str] = None


class SubscriptionContractCreate(SubscriptionContractBase):
    pass


class SubscriptionContractUpdate(SubscriptionContractBase):
    household_id: Optional[int] = None
    person_id: Optional[int] = None
    category: Optional[SubscriptionCategory] = None
    provider: Optional[str] = None
    product_name: Optional[str] = None
    contract_type: Optional[str] = None
    current_monthly_cost: Optional[float] = None
    promotional_cost: Optional[float] = None
    promotional_end_date: Optional[date] = None
    ordinary_cost: Optional[float] = None
    billing_frequency: Optional[IncomeFrequency] = None
    binding_start_date: Optional[date] = None
    binding_end_date: Optional[date] = None
    notice_period_days: Optional[int] = None
    auto_renew: Optional[bool] = None
    cancellation_method: Optional[str] = None
    cancellation_url: Optional[str] = None
    service_address: Optional[str] = None
    usage_metric_type: Optional[str] = None
    usage_metric_estimate: Optional[float] = None
    included_allowance: Optional[float] = None
    overage_risk: Optional[str] = None
    bundling_flag: Optional[bool] = None
    household_criticality: Optional[str] = None
    market_checkable: Optional[bool] = None
    last_negotiated_at: Optional[date] = None
    next_review_at: Optional[date] = None
    latest_invoice_doc_id: Optional[int] = None
    status: Optional[str] = None
    note: Optional[str] = None


class SubscriptionContractRead(SubscriptionContractBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# -------- InsurancePolicy --------
class InsurancePolicyBase(BaseModel):
    household_id: int
    type: str
    provider: str
    premium_monthly: float
    deductible: Optional[float] = None
    coverage_tier: Optional[str] = None
    renewal_date: Optional[date] = None
    binding_end_date: Optional[date] = None
    linked_asset_id: Optional[int] = None
    comparison_score: Optional[float] = None
    note: Optional[str] = None


class InsurancePolicyCreate(InsurancePolicyBase):
    pass


class InsurancePolicyUpdate(InsurancePolicyBase):
    household_id: Optional[int] = None
    type: Optional[str] = None
    provider: Optional[str] = None
    premium_monthly: Optional[float] = None
    deductible: Optional[float] = None
    coverage_tier: Optional[str] = None
    renewal_date: Optional[date] = None
    binding_end_date: Optional[date] = None
    linked_asset_id: Optional[int] = None
    comparison_score: Optional[float] = None
    note: Optional[str] = None


class InsurancePolicyRead(InsurancePolicyBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# -------- Vehicle --------
class VehicleBase(BaseModel):
    household_id: int
    owner_person_id: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    fuel_type: Optional[str] = None
    estimated_value: Optional[float] = None
    loan_id: Optional[int] = None
    insurance_policy_id: Optional[int] = None
    tax_monthly_estimate: Optional[float] = None
    fuel_monthly_estimate: Optional[float] = None
    service_monthly_estimate: Optional[float] = None
    parking_monthly_estimate: Optional[float] = None
    toll_monthly_estimate: Optional[float] = None
    tire_monthly_estimate: Optional[float] = None
    note: Optional[str] = None


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(VehicleBase):
    household_id: Optional[int] = None
    owner_person_id: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    fuel_type: Optional[str] = None
    estimated_value: Optional[float] = None
    loan_id: Optional[int] = None
    insurance_policy_id: Optional[int] = None
    tax_monthly_estimate: Optional[float] = None
    fuel_monthly_estimate: Optional[float] = None
    service_monthly_estimate: Optional[float] = None
    parking_monthly_estimate: Optional[float] = None
    toll_monthly_estimate: Optional[float] = None
    tire_monthly_estimate: Optional[float] = None
    note: Optional[str] = None


class VehicleRead(VehicleBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# -------- Asset --------
class AssetBase(BaseModel):
    household_id: int
    person_id: Optional[int] = None
    type: str
    institution: Optional[str] = None
    label: Optional[str] = None
    market_value: Optional[float] = None
    liquid_value: Optional[float] = None
    pledged: Optional[bool] = False
    updated_at: Optional[datetime] = None
    verification_doc_id: Optional[int] = None
    note: Optional[str] = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(AssetBase):
    household_id: Optional[int] = None
    person_id: Optional[int] = None
    type: Optional[str] = None
    institution: Optional[str] = None
    label: Optional[str] = None
    market_value: Optional[float] = None
    liquid_value: Optional[float] = None
    pledged: Optional[bool] = None
    updated_at: Optional[datetime] = None
    verification_doc_id: Optional[int] = None
    note: Optional[str] = None


class AssetRead(AssetBase):
    id: int
    # When reading assets we include ``updated_at`` from database
    updated_at: datetime
    class Config:
        orm_mode = True


# -------- HousingScenario --------
class HousingScenarioBase(BaseModel):
    household_id: int
    label: str
    purchase_price: Optional[float] = None
    down_payment: Optional[float] = None
    mortgage_needed: Optional[float] = None
    rate_assumption: Optional[float] = None
    amortization_rate: Optional[float] = None
    monthly_fee_or_operating_cost: Optional[float] = None
    monthly_insurance: Optional[float] = None
    monthly_property_cost_estimate: Optional[float] = None
    note: Optional[str] = None


class HousingScenarioCreate(HousingScenarioBase):
    pass


class HousingScenarioUpdate(HousingScenarioBase):
    household_id: Optional[int] = None
    label: Optional[str] = None
    purchase_price: Optional[float] = None
    down_payment: Optional[float] = None
    mortgage_needed: Optional[float] = None
    rate_assumption: Optional[float] = None
    amortization_rate: Optional[float] = None
    monthly_fee_or_operating_cost: Optional[float] = None
    monthly_insurance: Optional[float] = None
    monthly_property_cost_estimate: Optional[float] = None
    note: Optional[str] = None


class HousingScenarioRead(HousingScenarioBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# -------- Document --------
class DocumentBase(BaseModel):
    household_id: int
    document_type: str
    file_name: str
    mime_type: Optional[str] = None
    checksum: Optional[str] = None
    issuer: Optional[str] = None
    issue_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    total_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    currency: Optional[str] = None
    extracted_text: Optional[str] = None
    extraction_status: Optional[str] = Field(default="uploaded")
    processing_error: Optional[str] = None
    storage_path: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(DocumentBase):
    household_id: Optional[int] = None
    document_type: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    checksum: Optional[str] = None
    issuer: Optional[str] = None
    issue_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    total_amount: Optional[float] = None
    vat_amount: Optional[float] = None
    currency: Optional[str] = None
    extracted_text: Optional[str] = None
    extraction_status: Optional[str] = None
    processing_error: Optional[str] = None
    storage_path: Optional[str] = None


class DocumentRead(DocumentBase):
    id: int
    uploaded_at: datetime

    class Config:
        orm_mode = True


# -------- ExtractionDraft --------
class ExtractionDraftBase(BaseModel):
    household_id: int
    document_id: int
    target_entity_type: str
    proposed_json: Any
    review_json: Optional[Any] = None
    confidence: Optional[float] = None
    status: Optional[str] = Field(default="pending_review")
    model_name: Optional[str] = None
    canonical_target_entity_type: Optional[str] = None
    canonical_target_entity_id: Optional[int] = None
    review_error: Optional[str] = None
    apply_summary_json: Optional[Any] = None


class ExtractionDraftCreate(ExtractionDraftBase):
    pass


class ExtractionDraftUpdate(ExtractionDraftBase):
    household_id: Optional[int] = None
    document_id: Optional[int] = None
    target_entity_type: Optional[str] = None
    proposed_json: Optional[Any] = None
    review_json: Optional[Any] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    model_name: Optional[str] = None
    canonical_target_entity_type: Optional[str] = None
    canonical_target_entity_id: Optional[int] = None
    review_error: Optional[str] = None
    apply_summary_json: Optional[Any] = None


class ExtractionDraftRead(ExtractionDraftBase):
    id: int
    applied_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        orm_mode = True


class DocumentKeyFieldRead(BaseModel):
    key: str
    label: str
    value: str
    source: Literal["document", "draft_review", "draft_canonical", "canonical_record"]


class CanonicalLinkRead(BaseModel):
    draft_id: int
    target_entity_type: str
    target_entity_id: int
    target_label: str
    applied_at: Optional[datetime] = None


class DocumentEntityResolutionCandidateRead(BaseModel):
    entity_type: Literal["loan", "vehicle"]
    entity_id: Optional[int] = None
    label: str
    confidence: Optional[confloat(ge=0.0, le=1.0)] = None
    reason: Optional[str] = None
    recommended_action: Literal["link_existing", "create_new", "manual_review", "skip"] = "manual_review"


class DocumentEntityResolutionRead(BaseModel):
    draft_id: int
    primary_entity_type: Literal["loan", "vehicle", "subscription_contract", "recurring_cost", "income_source"]
    recommended_action: Literal["link_existing", "create_new", "manual_review", "skip"] = "manual_review"
    confidence: Optional[confloat(ge=0.0, le=1.0)] = None
    reason: Optional[str] = None
    loan_candidates: List[DocumentEntityResolutionCandidateRead] = Field(default_factory=list)
    vehicle_candidates: List[DocumentEntityResolutionCandidateRead] = Field(default_factory=list)


class DocumentApplyMutationRead(BaseModel):
    entity_type: str
    action: Literal["created", "updated", "linked", "skipped", "manual_review"]
    entity_id: Optional[int] = None
    label: str
    summary_sv: str


class DocumentApplySummaryRead(BaseModel):
    document_id: int
    draft_id: Optional[int] = None
    status: Literal["applied", "partial", "manual_review", "failed"]
    message_sv: str
    manual_actions_required: List[str] = Field(default_factory=list)
    mutations: List[DocumentApplyMutationRead] = Field(default_factory=list)
    applied_at: datetime


class DocumentWorkflowStepRead(BaseModel):
    key: str
    label_sv: str
    active: bool = False
    completed: bool = False


class DocumentWorkflowRead(BaseModel):
    document: DocumentRead
    workflow_status: Literal[
        "uploaded",
        "interpreting",
        "interpreted",
        "pending_review",
        "applied",
        "failed",
        "rejected",
        "manual_link_required",
        "deferred",
    ]
    status_detail: Optional[str] = None
    status_label_sv: Optional[str] = None
    status_steps: List[DocumentWorkflowStepRead] = Field(default_factory=list)
    drafts: List[ExtractionDraftRead] = Field(default_factory=list)
    key_fields: List[DocumentKeyFieldRead] = Field(default_factory=list)
    canonical_links: List[CanonicalLinkRead] = Field(default_factory=list)
    entity_resolutions: List[DocumentEntityResolutionRead] = Field(default_factory=list)
    apply_summary: Optional[DocumentApplySummaryRead] = None
    recommended_actions: List[str] = Field(default_factory=list)
    requires_manual_link: bool = False


class ExtractionDraftApplyRequest(BaseModel):
    action: Literal["create_new", "link_existing"] = "create_new"
    target_entity_id: Optional[int] = None
    proposed_json: Optional[Dict[str, Any]] = None

    @root_validator(allow_reuse=True)
    def validate_link_existing(cls, values):
        action = values.get("action")
        target_entity_id = values.get("target_entity_id")
        if action == "link_existing" and target_entity_id is None:
            raise ValueError("Skicka target_entity_id när draft ska kopplas till befintligt objekt.")
        return values


class DocumentDraftApplySelection(BaseModel):
    draft_id: int
    action: Literal["create_new", "link_existing", "skip"] = "create_new"
    target_entity_id: Optional[int] = None
    proposed_json: Optional[Dict[str, Any]] = None

    @root_validator(allow_reuse=True)
    def validate_selection(cls, values):
        action = values.get("action")
        target_entity_id = values.get("target_entity_id")
        if action == "link_existing" and target_entity_id is None:
            raise ValueError("Skicka target_entity_id när ett utkast ska kopplas till befintligt objekt.")
        return values


class RelatedEntityApplySelection(BaseModel):
    source_draft_id: int
    entity_type: Literal["vehicle"]
    action: Literal["create_new", "link_existing", "skip"] = "skip"
    target_entity_id: Optional[int] = None
    proposed_json: Optional[Dict[str, Any]] = None

    @root_validator(allow_reuse=True)
    def validate_related_selection(cls, values):
        action = values.get("action")
        target_entity_id = values.get("target_entity_id")
        if action == "link_existing" and target_entity_id is None:
            raise ValueError("Skicka target_entity_id när en relaterad koppling ska länkas till befintligt objekt.")
        return values


class DocumentApplyRequest(BaseModel):
    draft_ids: Optional[List[int]] = None
    action: Literal["create_new", "link_existing"] = "create_new"
    target_entity_id: Optional[int] = None
    proposed_json: Optional[Dict[str, Any]] = None
    draft_actions: List[DocumentDraftApplySelection] = Field(default_factory=list)
    related_actions: List[RelatedEntityApplySelection] = Field(default_factory=list)

    @root_validator(allow_reuse=True)
    def validate_document_apply(cls, values):
        action = values.get("action")
        target_entity_id = values.get("target_entity_id")
        draft_actions = values.get("draft_actions") or []
        if draft_actions:
            return values
        if action == "link_existing" and target_entity_id is None:
            raise ValueError("Skicka target_entity_id när dokumentet ska kopplas till befintligt objekt.")
        return values


class DocumentApplyResponse(BaseModel):
    document_id: int
    workflow_status: str
    status_label_sv: Optional[str] = None
    apply_summary: DocumentApplySummaryRead
    workflow: DocumentWorkflowRead


# -------- OptimizationOpportunity --------
class OptimizationOpportunityBase(BaseModel):
    household_id: int
    kind: str
    target_entity_type: str
    target_entity_id: int
    title: str
    rationale: Optional[str] = None
    estimated_monthly_saving: Optional[float] = None
    estimated_yearly_saving: Optional[float] = None
    confidence: Optional[float] = None
    effort_level: Optional[str] = Field(default="medium")
    risk_level: Optional[str] = Field(default="medium")
    reversibility: Optional[str] = Field(default="medium")
    evidence_json: Optional[Any] = None
    source_refs_json: Optional[Any] = None
    status: Optional[str] = Field(default="open")


class OptimizationOpportunityCreate(OptimizationOpportunityBase):
    pass


class OptimizationOpportunityUpdate(OptimizationOpportunityBase):
    household_id: Optional[int] = None
    kind: Optional[str] = None
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[int] = None
    title: Optional[str] = None
    rationale: Optional[str] = None
    estimated_monthly_saving: Optional[float] = None
    estimated_yearly_saving: Optional[float] = None
    confidence: Optional[float] = None
    effort_level: Optional[str] = None
    risk_level: Optional[str] = None
    reversibility: Optional[str] = None
    evidence_json: Optional[Any] = None
    source_refs_json: Optional[Any] = None
    status: Optional[str] = None


class OptimizationOpportunityRead(OptimizationOpportunityBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True


# -------- Scenario --------
class ScenarioBase(BaseModel):
    household_id: int
    label: str
    change_set_json: Any


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(ScenarioBase):
    household_id: Optional[int] = None
    label: Optional[str] = None
    change_set_json: Optional[Any] = None


class ScenarioRead(ScenarioBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True


# -------- ScenarioResult --------
class ScenarioResultBase(BaseModel):
    household_id: int
    scenario_id: int
    result_json: Any
    monthly_delta: Optional[float] = None
    yearly_delta: Optional[float] = None
    liquidity_delta: Optional[float] = None


class ScenarioResultCreate(ScenarioResultBase):
    pass


class ScenarioResultUpdate(ScenarioResultBase):
    household_id: Optional[int] = None
    scenario_id: Optional[int] = None
    result_json: Optional[Any] = None
    monthly_delta: Optional[float] = None
    yearly_delta: Optional[float] = None
    liquidity_delta: Optional[float] = None


class ScenarioResultRead(ScenarioResultBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True


# -------- ReportSnapshot --------
class ReportSnapshotBase(BaseModel):
    household_id: int
    type: str
    as_of_date: date
    assumption_json: Optional[Any] = None
    result_json: Any


class ReportSnapshotCreate(ReportSnapshotBase):
    pass


class ReportSnapshotUpdate(ReportSnapshotBase):
    household_id: Optional[int] = None
    type: Optional[str] = None
    as_of_date: Optional[date] = None
    assumption_json: Optional[Any] = None
    result_json: Optional[Any] = None


class ReportSnapshotRead(ReportSnapshotBase):
    id: int
    generated_at: datetime
    class Config:
        orm_mode = True


class RiskSignalRead(BaseModel):
    key: str
    severity: Literal["info", "warning", "critical"]
    message_sv: str


class HouseholdSummaryRead(BaseModel):
    household_id: int
    monthly_income: float
    monthly_income_net: float
    monthly_income_gross_only: float
    monthly_recurring_costs: float
    monthly_subscriptions: float
    monthly_insurance: float
    monthly_vehicle_costs: float
    monthly_loan_payments: float
    monthly_total_expenses: float
    monthly_net_cashflow: float
    yearly_income: float
    yearly_total_expenses: float
    yearly_net_cashflow: float
    asset_market_value: float
    asset_liquid_value: float
    loan_balance_total: float
    net_worth_estimate: float
    gross_income_only_entries: int
    counts: Dict[str, int]
    risk_signals: List[RiskSignalRead] = Field(default_factory=list)


class HousingScenarioEvaluationRead(BaseModel):
    scenario_id: int
    household_id: int
    label: str
    purchase_price: float
    down_payment: float
    mortgage_needed: float
    monthly_interest: float
    monthly_amortization: float
    monthly_operating_cost: float
    monthly_insurance: float
    monthly_property_cost_estimate: float
    monthly_total_cost: float
    yearly_total_cost: float


class ReportGenerateRequest(BaseModel):
    type: str = Field(default="monthly_overview")
    as_of_date: Optional[date] = None
    assumption_json: Optional[Any] = None


class ExtractionApplyRead(BaseModel):
    draft_id: int
    target_entity_type: str
    target_entity_id: int
    status: str
    summary: Optional[str] = None
    applied_entities: List[Dict[str, Any]] = Field(default_factory=list)
    manual_actions_required: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    applied_entities: List[DocumentApplyMutationRead] = Field(default_factory=list)
    manual_actions_required: List[str] = Field(default_factory=list)


class AssistantMessageRead(BaseModel):
    role: str
    content: str


class AssistantPromptRequest(BaseModel):
    prompt: str
    conversation: list[AssistantMessageRead] | None = None


class AIUsageRead(BaseModel):
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class AssistantWriteIntentRead(BaseModel):
    intent: Literal["create_expense", "create_income", "create_planned_purchase", "create_subscription", "delete_entity", "update_entity", "none"]
    target_entity_type: Optional[str] = None
    confidence: Optional[float] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    ambiguities: List[str] = Field(default_factory=list)


class AssistantPromptResponse(BaseModel):
    household_id: int
    prompt: str
    answer: str
    questions: List[str] = Field(default_factory=list)
    write_intent: Optional[AssistantWriteIntentRead] = None
    provider: str
    model: str
    usage: Optional[AIUsageRead] = None


class AssistantIntentApplyRequest(BaseModel):
    intent: Optional[str] = None
    target_entity_type: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    source_message_id: Optional[int] = None


# -------- MerchantAlias --------
class MerchantAliasCreate(BaseModel):
    household_id: int
    alias: str
    canonical_name: str
    category_hint: Optional[str] = None


class MerchantAliasRead(BaseModel):
    id: int
    household_id: int
    alias: str
    canonical_name: str
    category_hint: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class IngestSuggestionRead(BaseModel):
    target_entity_type: Literal["recurring_cost", "subscription_contract", "loan", "income_source"]
    review_bucket: Literal["recurring_cost", "subscription_contract", "loan", "income_source", "transfer_or_saving", "unclear"] = "unclear"
    title: str
    rationale: str
    confidence: Optional[confloat(ge=0.0, le=1.0)] = None
    proposed_json: Dict[str, Any]
    review_json: Dict[str, Any] = Field(default_factory=dict)
    validation_status: Literal["valid", "invalid"] = "valid"
    validation_errors: List[str] = Field(default_factory=list)
    uncertainty_notes: List[str] = Field(default_factory=list)
    duplicate_indicator: Optional[str] = None
    ownership_candidate: Optional[Literal["private", "shared", "unclear"]] = None
    why_suggested: Optional[str] = None


class IngestImageReadinessRead(BaseModel):
    supported: bool = True
    status: Literal["implemented", "not_implemented"] = "implemented"
    note: str = "OCR via Tesseract (swe+eng) för bilder och skannande PDF:er."


class IngestInputRead(BaseModel):
    source_channel: Literal["text", "pdf_text", "uploaded_document", "uploaded_pdf", "image", "bank_paste"]
    input_origin: Literal["user_paste", "document_text", "file_text", "pdf_text", "ocr_image", "ocr_pdf", "bank_paste"]
    document_id: Optional[int] = None
    document_file_name: Optional[str] = None
    source_name: Optional[str] = None
    text_length: int
    text_truncated: bool = False
    text_chunked: bool = False
    chunk_count: Optional[int] = None
    extraction_mode: str
    extraction_notes: List[str] = Field(default_factory=list)
    structured_data: Optional[Dict[str, Any]] = None


class IngestDocumentSummaryRead(BaseModel):
    document_type: Literal["subscription_contract", "invoice", "recurring_cost_candidate", "transfer_or_saving_candidate", "bank_row_batch", "insurance_policy", "loan_or_credit", "financial_note", "unclear"]
    provider_name: Optional[str] = None
    label: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    due_date: Optional[date] = None
    cadence: Optional[str] = None
    category_hint: Optional[str] = None
    suggested_target_entity_type: Optional[Literal["recurring_cost", "subscription_contract", "loan", "income_source"]] = None
    household_relevance: Literal["low", "medium", "high"] = "medium"
    confidence: Optional[confloat(ge=0.0, le=1.0)] = None
    confirmed_fields: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    uncertainty_reasons: List[str] = Field(default_factory=list)


class IngestReviewGroupRead(BaseModel):
    group_type: Literal["subscription_contract", "recurring_cost", "loan", "income_source", "transfer_or_saving", "unclear"]
    title: str
    summary: str
    confidence: Optional[confloat(ge=0.0, le=1.0)] = None
    suggestion_count: int
    uncertainty_reasons: List[str] = Field(default_factory=list)
    suggestions: List[IngestSuggestionRead] = Field(default_factory=list)


class IngestAnalyzeRequest(BaseModel):
    input_text: Optional[str] = None
    input_kind: Optional[str] = Field(default="unknown")
    source_channel: Literal["text", "pdf_text", "uploaded_document", "uploaded_pdf", "image", "bank_paste"] = "text"
    document_id: Optional[int] = None
    source_name: Optional[str] = None

    @root_validator(allow_reuse=True)
    def validate_input_source(cls, values):
        input_text = values.get("input_text")
        document_id = values.get("document_id")
        if not (input_text and input_text.strip()) and document_id is None:
            raise ValueError("Skicka input_text eller document_id till Data-In analyze.")
        return values


class IngestAnalyzeResponse(BaseModel):
    analysis_result_id: str
    household_id: int
    source_name: Optional[str] = None
    input_kind: str
    source_channel: Literal["text", "pdf_text", "uploaded_document", "uploaded_pdf", "image", "bank_paste"] = "text"
    document_id: Optional[int] = None
    input_details: IngestInputRead
    detected_kind: str
    document_summary: IngestDocumentSummaryRead
    review_groups: List[IngestReviewGroupRead] = Field(default_factory=list)
    summary: str
    guidance: List[str] = Field(default_factory=list)
    suggestions: List[IngestSuggestionRead] = Field(default_factory=list)
    image_readiness: IngestImageReadinessRead = Field(default_factory=IngestImageReadinessRead)
    provider: str
    model: str
    usage: Optional[AIUsageRead] = None


class IngestPromoteRequest(BaseModel):
    analysis_result_id: Optional[str] = None
    input_text: Optional[str] = None
    input_kind: Optional[str] = Field(default="unknown")
    source_channel: Literal["text", "pdf_text", "uploaded_document", "uploaded_pdf", "image", "bank_paste"] = "text"
    document_id: Optional[int] = None
    source_name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    detected_kind: Optional[str] = None
    document_summary: Optional[IngestDocumentSummaryRead] = None
    suggestions: List[IngestSuggestionRead] = Field(default_factory=list)

    @root_validator(allow_reuse=True)
    def validate_promote_source(cls, values):
        input_text = values.get("input_text")
        document_id = values.get("document_id")
        if not (input_text and input_text.strip()) and document_id is None:
            raise ValueError("Skicka input_text eller document_id till Data-In promote.")
        return values


class CreatedDraftRead(BaseModel):
    draft_id: int
    target_entity_type: str
    confidence: Optional[confloat(ge=0.0, le=1.0)] = None
    validation_status: str
    document_status: Optional[str] = None


class IngestPromoteResponse(BaseModel):
    analysis_result_id: str
    household_id: int
    document_id: int
    document_type: str
    created_drafts: List[CreatedDraftRead] = Field(default_factory=list)
    skipped_suggestions: int = 0
