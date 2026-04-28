"""
SQLAlchemy ORM models representing the household economics domain.

The datamodel is designed to capture a wide range of information about a
household's financial life, including income sources, loans, recurring costs,
subscriptions, insurance policies, assets, vehicles, scenarios and snapshot
reports. These models mirror the conceptual schema discussed in the
architectural specification to allow deterministic calculations and clear
separation between core data and derived data.

Relationships between entities use integer foreign keys to maintain
referential integrity. Cascading delete rules are conservative; child
records must typically be removed explicitly to prevent accidental data
loss. All models include an ``id`` primary key column and many include
timestamps for auditing and versioning purposes.

IMPORTANT: When adding or modifying fields, you should update the
corresponding Pydantic schemas and API endpoints to ensure consistency
between persisted data and external representations.
"""

import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Date,
    DateTime,
    JSON,
    ForeignKey,
    Enum,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class IncomeFrequency(str, enum.Enum):
    """Frequency enumeration for income and cost normalisation."""
    monthly = "monthly"
    yearly = "yearly"
    weekly = "weekly"
    biweekly = "biweekly"
    daily = "daily"


class LoanRepaymentModel(str, enum.Enum):
    """Repayment models for loans."""
    annuity = "annuity"
    fixed_amortization = "fixed_amortization"
    interest_only = "interest_only"
    manual = "manual"


class VariabilityClass(str, enum.Enum):
    """Classification of recurring cost variability."""
    fixed = "fixed"
    semi_fixed = "semi_fixed"
    variable = "variable"


class Controllability(str, enum.Enum):
    """How much control the household has over a cost or subscription."""
    locked = "locked"
    negotiable = "negotiable"
    reducible = "reducible"
    discretionary = "discretionary"


class SubscriptionCategory(str, enum.Enum):
    """High-level categories for subscription contracts."""
    mobile = "mobile"
    broadband = "broadband"
    electricity = "electricity"
    streaming = "streaming"
    gym = "gym"
    alarm = "alarm"
    software = "software"
    insurance = "insurance"
    membership = "membership"
    other = "other"


class AppUser(Base):
    __tablename__ = "app_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="users")
    sessions = relationship("AuthSession", back_populates="user", cascade="all, delete-orphan")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    user = relationship("AppUser", back_populates="sessions")


class ImportSession(Base):
    __tablename__ = "import_sessions"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    label = Column(String, nullable=False)
    status = Column(String, default="active")  # active, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="import_sessions")
    unresolved_questions = relationship("UnresolvedQuestion", back_populates="import_session", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="import_session")


class UnresolvedQuestion(Base):
    __tablename__ = "unresolved_questions"
    id = Column(Integer, primary_key=True, index=True)
    import_session_id = Column(Integer, ForeignKey("import_sessions.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String, nullable=False) # ownership, entity_type, categorization
    question_text = Column(String, nullable=False)
    related_refs = Column(JSON, nullable=True) # e.g. ["Kontoutdrag.xlsx:row=27"]
    confidence = Column(Float, nullable=True)
    answer = Column(Text, nullable=True)
    status = Column(String, default="pending") # pending, answered, ignored
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    import_session = relationship("ImportSession", back_populates="unresolved_questions")


class ChatThread(Base):
    __tablename__ = "chat_threads"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    label = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    household = relationship("Household", back_populates="chat_threads")
    messages = relationship(
        "ChatMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False) # "user", "assistant", "system"
    message_type = Column(String, nullable=False, default="message")
    content_text = Column(Text, nullable=False)
    content_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    thread = relationship("ChatThread", back_populates="messages")


class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    currency = Column(String, default="SEK")
    primary_country = Column(String, default="SE")
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    persons = relationship("Person", back_populates="household", cascade="all, delete-orphan")
    loans = relationship("Loan", back_populates="household", cascade="all, delete-orphan")
    recurring_costs = relationship("RecurringCost", back_populates="household", cascade="all, delete-orphan")
    subscriptions = relationship("SubscriptionContract", back_populates="household", cascade="all, delete-orphan")
    insurance_policies = relationship("InsurancePolicy", back_populates="household", cascade="all, delete-orphan")
    vehicles = relationship("Vehicle", back_populates="household", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="household", cascade="all, delete-orphan")
    scenarios = relationship("HousingScenario", back_populates="household", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="household", cascade="all, delete-orphan")
    extraction_drafts = relationship(
        "ExtractionDraft", back_populates="household", cascade="all, delete-orphan"
    )
    optimization_opportunities = relationship(
        "OptimizationOpportunity", back_populates="household", cascade="all, delete-orphan"
    )
    scenario_results = relationship(
        "ScenarioResult", back_populates="household", cascade="all, delete-orphan"
    )
    report_snapshots = relationship(
        "ReportSnapshot", back_populates="household", cascade="all, delete-orphan"
    )
    users = relationship("AppUser", back_populates="household")
    import_sessions = relationship("ImportSession", back_populates="household", cascade="all, delete-orphan")
    planned_purchases = relationship("PlannedPurchase", back_populates="household", cascade="all, delete-orphan")
    chat_threads = relationship("ChatThread", back_populates="household", cascade="all, delete-orphan")


class Person(Base):
    __tablename__ = "persons"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="self")  # self, partner, child, etc.
    income_share_mode = Column(String, default="pooled")  # exact, pooled, split
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="persons")
    income_sources = relationship(
        "IncomeSource", back_populates="person", cascade="all, delete-orphan"
    )


class IncomeSource(Base):
    __tablename__ = "income_sources"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # salary, csn, pension, benefit, freelance, other
    gross_amount = Column(Float, nullable=True)
    net_amount = Column(Float, nullable=True)
    frequency = Column(Enum(IncomeFrequency), default=IncomeFrequency.monthly)
    regularity = Column(String, default="fixed")  # fixed, variable
    source = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    verified = Column(Boolean, default=False)
    verification_doc_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    person = relationship("Person", back_populates="income_sources")
    verification_document = relationship("Document", foreign_keys=[verification_doc_id])


class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    type = Column(String, nullable=False)  # car, mortgage, credit_card, personal_loan, csn, other
    purpose = Column(String, nullable=True)
    lender = Column(String, nullable=True)
    original_amount = Column(Float, nullable=True)
    current_balance = Column(Float, nullable=True)
    remaining_term_months = Column(Integer, nullable=True)
    planned_end_date = Column(Date, nullable=True)
    nominal_rate = Column(Float, nullable=True)
    effective_rate = Column(Float, nullable=True)
    repayment_model = Column(Enum(LoanRepaymentModel), default=LoanRepaymentModel.annuity)
    required_monthly_payment = Column(Float, nullable=True)
    amortization_amount_monthly = Column(Float, nullable=True)
    due_day = Column(Integer, nullable=True)
    fixed_rate_until = Column(Date, nullable=True)
    secured = Column(Boolean, default=False)
    linked_asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    autopay = Column(Boolean, default=False)
    statement_doc_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    status = Column(String, default="active")  # active, closed, delinquent
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="loans")
    person = relationship("Person")
    linked_asset = relationship("Asset", foreign_keys=[linked_asset_id])
    statement_document = relationship("Document", foreign_keys=[statement_doc_id])


class RecurringCost(Base):
    __tablename__ = "recurring_costs"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    category = Column(String, nullable=False)  # groceries, fuel, childcare, etc.
    subcategory = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    frequency = Column(Enum(IncomeFrequency), default=IncomeFrequency.monthly)
    mandatory = Column(Boolean, default=True)
    variability_class = Column(Enum(VariabilityClass), default=VariabilityClass.fixed)
    controllability = Column(Enum(Controllability), default=Controllability.locked)
    vendor = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)
    due_day = Column(Integer, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    status = Column(String, default="active")  # active, ended, paused
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="recurring_costs")
    person = relationship("Person")


class SubscriptionContract(Base):
    __tablename__ = "subscription_contracts"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    category = Column(Enum(SubscriptionCategory), default=SubscriptionCategory.other)
    provider = Column(String, nullable=False)
    product_name = Column(String, nullable=True)
    contract_type = Column(String, nullable=False, default="subscription")
    current_monthly_cost = Column(Float, nullable=False)
    promotional_cost = Column(Float, nullable=True)
    promotional_end_date = Column(Date, nullable=True)
    ordinary_cost = Column(Float, nullable=True)
    billing_frequency = Column(Enum(IncomeFrequency), default=IncomeFrequency.monthly)
    binding_start_date = Column(Date, nullable=True)
    binding_end_date = Column(Date, nullable=True)
    notice_period_days = Column(Integer, nullable=True)
    auto_renew = Column(Boolean, default=True)
    cancellation_method = Column(String, nullable=True)
    cancellation_url = Column(String, nullable=True)
    service_address = Column(String, nullable=True)
    usage_metric_type = Column(String, nullable=True)
    usage_metric_estimate = Column(Float, nullable=True)
    included_allowance = Column(Float, nullable=True)
    overage_risk = Column(String, nullable=True)
    bundling_flag = Column(Boolean, default=False)
    household_criticality = Column(String, default="optional")  # critical, useful, optional, dead_weight
    market_checkable = Column(Boolean, default=True)
    last_negotiated_at = Column(Date, nullable=True)
    next_review_at = Column(Date, nullable=True)
    latest_invoice_doc_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    note = Column(Text, nullable=True)
    status = Column(String, default="active")  # active, ended, paused
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="subscriptions")
    person = relationship("Person")
    latest_invoice_document = relationship("Document", foreign_keys=[latest_invoice_doc_id])


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # home, car, pet, accident, life, child
    provider = Column(String, nullable=False)
    premium_monthly = Column(Float, nullable=False)
    deductible = Column(Float, nullable=True)
    coverage_tier = Column(String, nullable=True)
    renewal_date = Column(Date, nullable=True)
    binding_end_date = Column(Date, nullable=True)
    linked_asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    comparison_score = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="insurance_policies")
    linked_asset = relationship("Asset", foreign_keys=[linked_asset_id])


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    owner_person_id = Column(Integer, ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    make = Column(String, nullable=True)
    model = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    fuel_type = Column(String, nullable=True)
    estimated_value = Column(Float, nullable=True)
    loan_id = Column(Integer, ForeignKey("loans.id", ondelete="SET NULL"), nullable=True)
    insurance_policy_id = Column(Integer, ForeignKey("insurance_policies.id", ondelete="SET NULL"), nullable=True)
    tax_monthly_estimate = Column(Float, nullable=True)
    fuel_monthly_estimate = Column(Float, nullable=True)
    service_monthly_estimate = Column(Float, nullable=True)
    parking_monthly_estimate = Column(Float, nullable=True)
    toll_monthly_estimate = Column(Float, nullable=True)
    tire_monthly_estimate = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="vehicles")
    owner_person = relationship("Person", foreign_keys=[owner_person_id])
    loan = relationship("Loan", foreign_keys=[loan_id])
    insurance_policy = relationship("InsurancePolicy", foreign_keys=[insurance_policy_id])


class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    type = Column(String, nullable=False)  # checking, savings, fund, car, house, cash, other
    institution = Column(String, nullable=True)
    label = Column(String, nullable=True)
    market_value = Column(Float, nullable=True)
    liquid_value = Column(Float, nullable=True)
    pledged = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)
    verification_doc_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    note = Column(Text, nullable=True)
    # Relationships
    household = relationship("Household", back_populates="assets")
    person = relationship("Person")
    verification_document = relationship("Document", foreign_keys=[verification_doc_id])


class HousingScenario(Base):
    __tablename__ = "housing_scenarios"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    label = Column(String, nullable=False)
    purchase_price = Column(Float, nullable=True)
    down_payment = Column(Float, nullable=True)
    mortgage_needed = Column(Float, nullable=True)
    rate_assumption = Column(Float, nullable=True)
    amortization_rate = Column(Float, nullable=True)
    monthly_fee_or_operating_cost = Column(Float, nullable=True)
    monthly_insurance = Column(Float, nullable=True)
    monthly_property_cost_estimate = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="scenarios")


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String, nullable=False)  # receipt, invoice, contract, payslip, bank_statement, loan_statement
    file_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    checksum = Column(String, nullable=True)
    issuer = Column(String, nullable=True)
    issue_date = Column(Date, nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    total_amount = Column(Float, nullable=True)
    vat_amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    extracted_text = Column(Text, nullable=True)
    extraction_status = Column(String, default="uploaded")  # uploaded, interpreted, pending_review, applied, failed
    processing_error = Column(Text, nullable=True)
    storage_path = Column(String, nullable=True)
    import_session_id = Column(Integer, ForeignKey("import_sessions.id", ondelete="SET NULL"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="documents")
    import_session = relationship("ImportSession", back_populates="documents")

    extraction_drafts = relationship(
        "ExtractionDraft", back_populates="document", cascade="all, delete-orphan"
    )


class IngestAnalysisResult(Base):
    __tablename__ = "ingest_analysis_results"
    id = Column(Integer, primary_key=True, index=True)
    analysis_result_id = Column(String, unique=True, index=True, nullable=False)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    source_hash = Column(String, nullable=False)
    source_channel = Column(String, nullable=False)
    source_name = Column(String, nullable=True)
    normalized_suggestions = Column(JSON, nullable=False)
    document_summary = Column(JSON, nullable=True)
    detected_kind = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    analysis_schema_version = Column(String, nullable=False, default="ingest-analysis-v1")
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household")
    document = relationship("Document")


class ExtractionDraft(Base):
    __tablename__ = "extraction_drafts"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    target_entity_type = Column(String, nullable=False)  # transaction, contract, loan, insurance, income
    proposed_json = Column(JSON, nullable=False)
    review_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(String, default="pending_review")  # pending_review, deferred, approved, rejected, apply_failed
    model_name = Column(String, nullable=True)
    canonical_target_entity_type = Column(String, nullable=True)
    canonical_target_entity_id = Column(Integer, nullable=True)
    review_error = Column(Text, nullable=True)
    apply_summary_json = Column(JSON, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="extraction_drafts")
    document = relationship("Document", back_populates="extraction_drafts")


class OptimizationOpportunity(Base):
    __tablename__ = "optimization_opportunities"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String, nullable=False)  # cancel, renegotiate, switch_provider, reduce_usage, consolidate_debt
    target_entity_type = Column(String, nullable=False)
    target_entity_id = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    rationale = Column(Text, nullable=True)
    estimated_monthly_saving = Column(Float, nullable=True)
    estimated_yearly_saving = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    effort_level = Column(String, default="medium")
    risk_level = Column(String, default="medium")
    reversibility = Column(String, default="medium")
    evidence_json = Column(JSON, nullable=True)
    source_refs_json = Column(JSON, nullable=True)
    status = Column(String, default="open")  # open, accepted, dismissed, done
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="optimization_opportunities")


class Scenario(Base):
    __tablename__ = "scenarios"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    label = Column(String, nullable=False)
    change_set_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household")
    results = relationship(
        "ScenarioResult", back_populates="scenario", cascade="all, delete-orphan"
    )


class ScenarioResult(Base):
    __tablename__ = "scenario_results"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False)
    result_json = Column(JSON, nullable=False)
    monthly_delta = Column(Float, nullable=True)
    yearly_delta = Column(Float, nullable=True)
    liquidity_delta = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="scenario_results")
    scenario = relationship("Scenario", back_populates="results")


class MerchantAlias(Base):
    __tablename__ = "merchant_aliases"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String, nullable=False)
    canonical_name = Column(String, nullable=False)
    category_hint = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    household = relationship("Household")


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # monthly_overview, bank_calc, optimization_report
    as_of_date = Column(Date, nullable=False)
    assumption_json = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="report_snapshots")


class PlannedPurchase(Base):
    """A planned future purchase tracked for affordability analysis."""
    __tablename__ = "planned_purchases"
    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=True)
    estimated_amount = Column(Float, nullable=False, default=0.0)
    priority = Column(String, nullable=False, default="optional")  # essential / important / optional
    due_window = Column(String, nullable=True)  # e.g. "2026-05", "this_cycle", "next_month"
    status = Column(String, nullable=False, default="planned")  # planned / committed / done / deferred
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    household = relationship("Household", back_populates="planned_purchases")
    person = relationship("Person")
