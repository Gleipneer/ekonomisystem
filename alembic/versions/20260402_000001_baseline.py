"""baseline schema

Revision ID: 20260402_000001
Revises:
Create Date: 2026-04-02 15:50:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260402_000001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


income_frequency = sa.Enum(
    "monthly",
    "yearly",
    "weekly",
    "biweekly",
    "daily",
    name="incomefrequency",
)
loan_repayment_model = sa.Enum(
    "annuity",
    "fixed_amortization",
    "interest_only",
    "manual",
    name="loanrepaymentmodel",
)
variability_class = sa.Enum("fixed", "semi_fixed", "variable", name="variabilityclass")
controllability = sa.Enum(
    "locked",
    "negotiable",
    "reducible",
    "discretionary",
    name="controllability",
)
subscription_category = sa.Enum(
    "mobile",
    "broadband",
    "electricity",
    "streaming",
    "gym",
    "alarm",
    "software",
    "insurance",
    "membership",
    "other",
    name="subscriptioncategory",
)


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "households"):
        op.create_table(
            "households",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("currency", sa.String(), nullable=True),
            sa.Column("primary_country", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "persons"):
        op.create_table(
            "persons",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=True),
            sa.Column("income_share_mode", sa.String(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "documents"):
        op.create_table(
            "documents",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("document_type", sa.String(), nullable=False),
            sa.Column("file_name", sa.String(), nullable=False),
            sa.Column("mime_type", sa.String(), nullable=True),
            sa.Column("checksum", sa.String(), nullable=True),
            sa.Column("issuer", sa.String(), nullable=True),
            sa.Column("issue_date", sa.Date(), nullable=True),
            sa.Column("period_start", sa.Date(), nullable=True),
            sa.Column("period_end", sa.Date(), nullable=True),
            sa.Column("total_amount", sa.Float(), nullable=True),
            sa.Column("vat_amount", sa.Float(), nullable=True),
            sa.Column("currency", sa.String(), nullable=True),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("extraction_status", sa.String(), nullable=True),
            sa.Column("storage_path", sa.String(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "assets"):
        op.create_table(
            "assets",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=True),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("institution", sa.String(), nullable=True),
            sa.Column("label", sa.String(), nullable=True),
            sa.Column("market_value", sa.Float(), nullable=True),
            sa.Column("liquid_value", sa.Float(), nullable=True),
            sa.Column("pledged", sa.Boolean(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("verification_doc_id", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["verification_doc_id"], ["documents.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "income_sources"):
        op.create_table(
            "income_sources",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("gross_amount", sa.Float(), nullable=True),
            sa.Column("net_amount", sa.Float(), nullable=True),
            sa.Column("frequency", income_frequency, nullable=True),
            sa.Column("regularity", sa.String(), nullable=True),
            sa.Column("source", sa.String(), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("verified", sa.Boolean(), nullable=True),
            sa.Column("verification_doc_id", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["verification_doc_id"], ["documents.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "loans"):
        op.create_table(
            "loans",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=True),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("purpose", sa.String(), nullable=True),
            sa.Column("lender", sa.String(), nullable=True),
            sa.Column("original_amount", sa.Float(), nullable=True),
            sa.Column("current_balance", sa.Float(), nullable=True),
            sa.Column("remaining_term_months", sa.Integer(), nullable=True),
            sa.Column("planned_end_date", sa.Date(), nullable=True),
            sa.Column("nominal_rate", sa.Float(), nullable=True),
            sa.Column("effective_rate", sa.Float(), nullable=True),
            sa.Column("repayment_model", loan_repayment_model, nullable=True),
            sa.Column("required_monthly_payment", sa.Float(), nullable=True),
            sa.Column("amortization_amount_monthly", sa.Float(), nullable=True),
            sa.Column("due_day", sa.Integer(), nullable=True),
            sa.Column("fixed_rate_until", sa.Date(), nullable=True),
            sa.Column("secured", sa.Boolean(), nullable=True),
            sa.Column("linked_asset_id", sa.Integer(), nullable=True),
            sa.Column("autopay", sa.Boolean(), nullable=True),
            sa.Column("statement_doc_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["linked_asset_id"], ["assets.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["statement_doc_id"], ["documents.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "recurring_costs"):
        op.create_table(
            "recurring_costs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=True),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("subcategory", sa.String(), nullable=True),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("frequency", income_frequency, nullable=True),
            sa.Column("mandatory", sa.Boolean(), nullable=True),
            sa.Column("variability_class", variability_class, nullable=True),
            sa.Column("controllability", controllability, nullable=True),
            sa.Column("vendor", sa.String(), nullable=True),
            sa.Column("payment_method", sa.String(), nullable=True),
            sa.Column("due_day", sa.Integer(), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "subscription_contracts"):
        op.create_table(
            "subscription_contracts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=True),
            sa.Column("category", subscription_category, nullable=True),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("product_name", sa.String(), nullable=True),
            sa.Column("contract_type", sa.String(), nullable=False),
            sa.Column("current_monthly_cost", sa.Float(), nullable=False),
            sa.Column("promotional_cost", sa.Float(), nullable=True),
            sa.Column("promotional_end_date", sa.Date(), nullable=True),
            sa.Column("ordinary_cost", sa.Float(), nullable=True),
            sa.Column("billing_frequency", income_frequency, nullable=True),
            sa.Column("binding_start_date", sa.Date(), nullable=True),
            sa.Column("binding_end_date", sa.Date(), nullable=True),
            sa.Column("notice_period_days", sa.Integer(), nullable=True),
            sa.Column("auto_renew", sa.Boolean(), nullable=True),
            sa.Column("cancellation_method", sa.String(), nullable=True),
            sa.Column("cancellation_url", sa.String(), nullable=True),
            sa.Column("service_address", sa.String(), nullable=True),
            sa.Column("usage_metric_type", sa.String(), nullable=True),
            sa.Column("usage_metric_estimate", sa.Float(), nullable=True),
            sa.Column("included_allowance", sa.Float(), nullable=True),
            sa.Column("overage_risk", sa.String(), nullable=True),
            sa.Column("bundling_flag", sa.Boolean(), nullable=True),
            sa.Column("household_criticality", sa.String(), nullable=True),
            sa.Column("market_checkable", sa.Boolean(), nullable=True),
            sa.Column("last_negotiated_at", sa.Date(), nullable=True),
            sa.Column("next_review_at", sa.Date(), nullable=True),
            sa.Column("latest_invoice_doc_id", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["latest_invoice_doc_id"], ["documents.id"]),
            sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "insurance_policies"):
        op.create_table(
            "insurance_policies",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("premium_monthly", sa.Float(), nullable=False),
            sa.Column("deductible", sa.Float(), nullable=True),
            sa.Column("coverage_tier", sa.String(), nullable=True),
            sa.Column("renewal_date", sa.Date(), nullable=True),
            sa.Column("binding_end_date", sa.Date(), nullable=True),
            sa.Column("linked_asset_id", sa.Integer(), nullable=True),
            sa.Column("comparison_score", sa.Float(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["linked_asset_id"], ["assets.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "vehicles"):
        op.create_table(
            "vehicles",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("owner_person_id", sa.Integer(), nullable=True),
            sa.Column("make", sa.String(), nullable=True),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("year", sa.Integer(), nullable=True),
            sa.Column("fuel_type", sa.String(), nullable=True),
            sa.Column("estimated_value", sa.Float(), nullable=True),
            sa.Column("loan_id", sa.Integer(), nullable=True),
            sa.Column("insurance_policy_id", sa.Integer(), nullable=True),
            sa.Column("tax_monthly_estimate", sa.Float(), nullable=True),
            sa.Column("fuel_monthly_estimate", sa.Float(), nullable=True),
            sa.Column("service_monthly_estimate", sa.Float(), nullable=True),
            sa.Column("parking_monthly_estimate", sa.Float(), nullable=True),
            sa.Column("toll_monthly_estimate", sa.Float(), nullable=True),
            sa.Column("tire_monthly_estimate", sa.Float(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["insurance_policy_id"], ["insurance_policies.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["loan_id"], ["loans.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["owner_person_id"], ["persons.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "housing_scenarios"):
        op.create_table(
            "housing_scenarios",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("purchase_price", sa.Float(), nullable=True),
            sa.Column("down_payment", sa.Float(), nullable=True),
            sa.Column("mortgage_needed", sa.Float(), nullable=True),
            sa.Column("rate_assumption", sa.Float(), nullable=True),
            sa.Column("amortization_rate", sa.Float(), nullable=True),
            sa.Column("monthly_fee_or_operating_cost", sa.Float(), nullable=True),
            sa.Column("monthly_insurance", sa.Float(), nullable=True),
            sa.Column("monthly_property_cost_estimate", sa.Float(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "extraction_drafts"):
        op.create_table(
            "extraction_drafts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("target_entity_type", sa.String(), nullable=False),
            sa.Column("proposed_json", sa.JSON(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("model_name", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "optimization_opportunities"):
        op.create_table(
            "optimization_opportunities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("target_entity_type", sa.String(), nullable=False),
            sa.Column("target_entity_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("estimated_monthly_saving", sa.Float(), nullable=True),
            sa.Column("estimated_yearly_saving", sa.Float(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("effort_level", sa.String(), nullable=True),
            sa.Column("risk_level", sa.String(), nullable=True),
            sa.Column("reversibility", sa.String(), nullable=True),
            sa.Column("evidence_json", sa.JSON(), nullable=True),
            sa.Column("source_refs_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "scenarios"):
        op.create_table(
            "scenarios",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("change_set_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "scenario_results"):
        op.create_table(
            "scenario_results",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("scenario_id", sa.Integer(), nullable=False),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column("monthly_delta", sa.Float(), nullable=True),
            sa.Column("yearly_delta", sa.Float(), nullable=True),
            sa.Column("liquidity_delta", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table(inspector, "report_snapshots"):
        op.create_table(
            "report_snapshots",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("household_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("as_of_date", sa.Date(), nullable=False),
            sa.Column("assumption_json", sa.JSON(), nullable=True),
            sa.Column("result_json", sa.JSON(), nullable=False),
            sa.Column("generated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    for table_name in [
        "households",
        "persons",
        "income_sources",
        "loans",
        "recurring_costs",
        "subscription_contracts",
        "insurance_policies",
        "vehicles",
        "assets",
        "housing_scenarios",
        "documents",
        "extraction_drafts",
        "optimization_opportunities",
        "scenarios",
        "scenario_results",
        "report_snapshots",
    ]:
        index_name = f"ix_{table_name}_id"
        if _has_table(inspector, table_name) and not _has_index(inspector, table_name, index_name):
            op.create_index(index_name, table_name, ["id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in [
        "report_snapshots",
        "scenario_results",
        "scenarios",
        "optimization_opportunities",
        "extraction_drafts",
        "housing_scenarios",
        "vehicles",
        "insurance_policies",
        "subscription_contracts",
        "recurring_costs",
        "loans",
        "income_sources",
        "assets",
        "documents",
        "persons",
        "households",
    ]:
        index_name = f"ix_{table_name}_id"
        if _has_table(inspector, table_name) and _has_index(inspector, table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
        if _has_table(inspector, table_name):
            op.drop_table(table_name)
        inspector = sa.inspect(bind)
