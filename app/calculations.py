from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from . import models


MONTHS_PER_YEAR = 12
WEEKS_PER_YEAR = 52
BIWEEKS_PER_YEAR = 26
DAYS_PER_YEAR = 365


def amount_to_monthly(amount: float | None, frequency: models.IncomeFrequency | str | None) -> float:
    if amount is None:
        return 0.0

    frequency_value = frequency.value if hasattr(frequency, "value") else frequency
    if frequency_value == models.IncomeFrequency.yearly.value:
        return float(amount) / MONTHS_PER_YEAR
    if frequency_value == models.IncomeFrequency.weekly.value:
        return float(amount) * WEEKS_PER_YEAR / MONTHS_PER_YEAR
    if frequency_value == models.IncomeFrequency.biweekly.value:
        return float(amount) * BIWEEKS_PER_YEAR / MONTHS_PER_YEAR
    if frequency_value == models.IncomeFrequency.daily.value:
        return float(amount) * DAYS_PER_YEAR / MONTHS_PER_YEAR
    return float(amount)


def amount_to_yearly(amount: float | None, frequency: models.IncomeFrequency | str | None) -> float:
    return amount_to_monthly(amount, frequency) * MONTHS_PER_YEAR


def estimate_loan_monthly_payment(loan: models.Loan | dict[str, Any]) -> float:
    get = loan.get if isinstance(loan, dict) else lambda key, default=None: getattr(loan, key, default)
    required_payment = get("required_monthly_payment")
    if required_payment is not None:
        return float(required_payment)

    current_balance = float(get("current_balance") or 0.0)
    nominal_rate = float(get("nominal_rate") or 0.0)
    amortization = float(get("amortization_amount_monthly") or 0.0)
    monthly_interest = current_balance * (nominal_rate / 100.0) / MONTHS_PER_YEAR
    return monthly_interest + amortization


def estimate_vehicle_monthly_cost(vehicle: models.Vehicle | dict[str, Any]) -> float:
    get = vehicle.get if isinstance(vehicle, dict) else lambda key, default=None: getattr(vehicle, key, default)
    keys = (
        "tax_monthly_estimate",
        "fuel_monthly_estimate",
        "service_monthly_estimate",
        "parking_monthly_estimate",
        "toll_monthly_estimate",
        "tire_monthly_estimate",
    )
    return sum(float(get(key) or 0.0) for key in keys)


def serialize_model(instance: Any) -> dict[str, Any]:
    return {column.name: getattr(instance, column.name) for column in instance.__table__.columns}


def load_household_records(db: Session, household_id: int) -> dict[str, list[dict[str, Any]]]:
    incomes = (
        db.query(models.IncomeSource)
        .join(models.Person, models.IncomeSource.person_id == models.Person.id)
        .filter(models.Person.household_id == household_id)
        .all()
    )

    return {
        "households": [serialize_model(db.get(models.Household, household_id))],
        "persons": [serialize_model(item) for item in db.query(models.Person).filter_by(household_id=household_id).all()],
        "income_sources": [serialize_model(item) for item in incomes],
        "loans": [serialize_model(item) for item in db.query(models.Loan).filter_by(household_id=household_id).all()],
        "recurring_costs": [
            serialize_model(item) for item in db.query(models.RecurringCost).filter_by(household_id=household_id).all()
        ],
        "subscription_contracts": [
            serialize_model(item)
            for item in db.query(models.SubscriptionContract).filter_by(household_id=household_id).all()
        ],
        "insurance_policies": [
            serialize_model(item) for item in db.query(models.InsurancePolicy).filter_by(household_id=household_id).all()
        ],
        "vehicles": [serialize_model(item) for item in db.query(models.Vehicle).filter_by(household_id=household_id).all()],
        "assets": [serialize_model(item) for item in db.query(models.Asset).filter_by(household_id=household_id).all()],
        "documents": [serialize_model(item) for item in db.query(models.Document).filter_by(household_id=household_id).all()],
        "extraction_drafts": [
            serialize_model(item) for item in db.query(models.ExtractionDraft).filter_by(household_id=household_id).all()
        ],
        "optimization_opportunities": [
            serialize_model(item)
            for item in db.query(models.OptimizationOpportunity).filter_by(household_id=household_id).all()
        ],
        "scenarios": [serialize_model(item) for item in db.query(models.Scenario).filter_by(household_id=household_id).all()],
        "scenario_results": [
            serialize_model(item) for item in db.query(models.ScenarioResult).filter_by(household_id=household_id).all()
        ],
        "report_snapshots": [
            serialize_model(item) for item in db.query(models.ReportSnapshot).filter_by(household_id=household_id).all()
        ],
    }


def _build_risk_signals(
    *,
    monthly_income: float,
    monthly_total_expenses: float,
    monthly_net_cashflow: float,
    monthly_subscriptions: float,
    loan_balance_total: float,
    gross_income_only_entries: int,
    records: dict[str, list[dict[str, Any]]],
) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []

    if monthly_income > 0 and monthly_net_cashflow < monthly_income * 0.1:
        signals.append({"key": "low_margin", "severity": "warning", "message_sv": f"Låg marginal: kassaflödet är bara {round(monthly_net_cashflow):,} kr/mån efter utgifter.".replace(",", " ")})

    if monthly_income > 0 and monthly_net_cashflow < 0:
        signals.append({"key": "negative_cashflow", "severity": "critical", "message_sv": "Negativt kassaflöde: utgifterna överstiger inkomsterna."})

    if monthly_income > 0 and monthly_total_expenses > monthly_income * 0.85:
        pct = round(monthly_total_expenses / monthly_income * 100)
        signals.append({"key": "high_fixed_ratio", "severity": "warning", "message_sv": f"Hög andel bundna kostnader: {pct} % av inkomsten går till fasta utgifter."})

    if monthly_income > 0 and monthly_subscriptions > monthly_income * 0.15:
        signals.append({"key": "high_subscription_cost", "severity": "info", "message_sv": f"Abonnemangskostnad {round(monthly_subscriptions):,} kr/mån — överväg granskning.".replace(",", " ")})

    if loan_balance_total > 0 and monthly_income > 0:
        debt_ratio = loan_balance_total / (monthly_income * MONTHS_PER_YEAR)
        if debt_ratio > 4.5:
            signals.append({"key": "high_debt_ratio", "severity": "critical", "message_sv": f"Hög skuldsättning: skuld/årsinkomst = {debt_ratio:.1f}x."})
        elif debt_ratio > 3:
            signals.append({"key": "elevated_debt_ratio", "severity": "warning", "message_sv": f"Förhöjd skuldsättning: skuld/årsinkomst = {debt_ratio:.1f}x."})

    if gross_income_only_entries > 0:
        signals.append({"key": "unverified_income", "severity": "info", "message_sv": f"{gross_income_only_entries} inkomstkälla(or) saknar nettobelopp och visas med brutto."})

    pending_drafts = sum(1 for d in records.get("extraction_drafts", []) if d.get("status") == "pending_review")
    if pending_drafts > 0:
        signals.append({"key": "pending_reviews", "severity": "info", "message_sv": f"{pending_drafts} reviewutkast väntar på granskning."})

    if not records.get("income_sources"):
        signals.append({"key": "no_income", "severity": "warning", "message_sv": "Inga inkomstkällor registrerade."})

    return signals


def build_household_summary(records: dict[str, list[dict[str, Any]]], household_id: int) -> dict[str, Any]:
    monthly_income_net = sum(
        amount_to_monthly(item.get("net_amount"), item.get("frequency"))
        for item in records["income_sources"]
        if item.get("net_amount") is not None
    )
    monthly_income_gross_only = sum(
        amount_to_monthly(item.get("gross_amount"), item.get("frequency"))
        for item in records["income_sources"]
        if item.get("net_amount") is None and item.get("gross_amount") is not None
    )
    gross_income_only_entries = sum(
        1 for item in records["income_sources"] if item.get("net_amount") is None and item.get("gross_amount") is not None
    )
    monthly_income = monthly_income_net + monthly_income_gross_only
    monthly_recurring_costs = sum(
        amount_to_monthly(item.get("amount"), item.get("frequency")) for item in records["recurring_costs"]
    )
    monthly_subscriptions = sum(
        amount_to_monthly(item.get("current_monthly_cost"), item.get("billing_frequency"))
        for item in records["subscription_contracts"]
    )
    monthly_insurance = sum(float(item.get("premium_monthly") or 0.0) for item in records["insurance_policies"])
    monthly_vehicle_costs = sum(estimate_vehicle_monthly_cost(item) for item in records["vehicles"])
    monthly_loan_payments = sum(estimate_loan_monthly_payment(item) for item in records["loans"])

    monthly_total_expenses = (
        monthly_recurring_costs
        + monthly_subscriptions
        + monthly_insurance
        + monthly_vehicle_costs
        + monthly_loan_payments
    )
    monthly_net_cashflow = monthly_income - monthly_total_expenses
    yearly_income = monthly_income * MONTHS_PER_YEAR
    yearly_total_expenses = monthly_total_expenses * MONTHS_PER_YEAR
    yearly_net_cashflow = monthly_net_cashflow * MONTHS_PER_YEAR
    asset_market_value = sum(float(item.get("market_value") or 0.0) for item in records["assets"])
    asset_liquid_value = sum(float(item.get("liquid_value") or 0.0) for item in records["assets"])
    loan_balance_total = sum(float(item.get("current_balance") or 0.0) for item in records["loans"])
    net_worth_estimate = asset_market_value - loan_balance_total

    risk_signals = _build_risk_signals(
        monthly_income=monthly_income,
        monthly_total_expenses=monthly_total_expenses,
        monthly_net_cashflow=monthly_net_cashflow,
        monthly_subscriptions=monthly_subscriptions,
        loan_balance_total=loan_balance_total,
        gross_income_only_entries=gross_income_only_entries,
        records=records,
    )

    return {
        "household_id": household_id,
        "monthly_income": round(monthly_income, 2),
        "monthly_income_net": round(monthly_income_net, 2),
        "monthly_income_gross_only": round(monthly_income_gross_only, 2),
        "monthly_recurring_costs": round(monthly_recurring_costs, 2),
        "monthly_subscriptions": round(monthly_subscriptions, 2),
        "monthly_insurance": round(monthly_insurance, 2),
        "monthly_vehicle_costs": round(monthly_vehicle_costs, 2),
        "monthly_loan_payments": round(monthly_loan_payments, 2),
        "monthly_total_expenses": round(monthly_total_expenses, 2),
        "monthly_net_cashflow": round(monthly_net_cashflow, 2),
        "yearly_income": round(yearly_income, 2),
        "yearly_total_expenses": round(yearly_total_expenses, 2),
        "yearly_net_cashflow": round(yearly_net_cashflow, 2),
        "asset_market_value": round(asset_market_value, 2),
        "asset_liquid_value": round(asset_liquid_value, 2),
        "loan_balance_total": round(loan_balance_total, 2),
        "net_worth_estimate": round(net_worth_estimate, 2),
        "gross_income_only_entries": gross_income_only_entries,
        "risk_signals": risk_signals,
        "counts": {
            "persons": len(records["persons"]),
            "income_sources": len(records["income_sources"]),
            "loans": len(records["loans"]),
            "recurring_costs": len(records["recurring_costs"]),
            "subscription_contracts": len(records["subscription_contracts"]),
            "insurance_policies": len(records["insurance_policies"]),
            "vehicles": len(records["vehicles"]),
            "assets": len(records["assets"]),
            "documents": len(records["documents"]),
            "extraction_drafts": len(records["extraction_drafts"]),
            "optimization_opportunities": len(records["optimization_opportunities"]),
            "scenarios": len(records["scenarios"]),
            "scenario_results": len(records["scenario_results"]),
            "report_snapshots": len(records["report_snapshots"]),
        },
    }


def apply_scenario_adjustments(records: dict[str, list[dict[str, Any]]], adjustments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    projected = {entity: [item.copy() for item in items] for entity, items in records.items()}

    for adjustment in adjustments:
        entity = adjustment.get("entity")
        operation = adjustment.get("operation", "set")
        record_id = adjustment.get("id")
        changes = adjustment.get("changes")
        field = adjustment.get("field")
        value = adjustment.get("value")

        if entity not in projected:
            continue

        if operation == "create":
            new_item = dict(changes or {})
            if "id" not in new_item:
                next_id = max((item.get("id", 0) for item in projected[entity]), default=0) + 1
                new_item["id"] = next_id
            projected[entity].append(new_item)
            continue

        if operation == "delete":
            projected[entity] = [item for item in projected[entity] if item.get("id") != record_id]
            continue

        target = next((item for item in projected[entity] if item.get("id") == record_id), None)
        if target is None:
            continue

        if operation == "delta" and field:
            target[field] = float(target.get(field) or 0.0) + float(value or 0.0)
            continue

        if changes:
            target.update(changes)
            continue

        if field:
            target[field] = value

    return projected


def evaluate_housing_scenario(scenario: models.HousingScenario) -> dict[str, Any]:
    mortgage_needed = float(scenario.mortgage_needed or 0.0)
    rate_assumption = float(scenario.rate_assumption or 0.0) / 100.0
    amortization_rate = float(scenario.amortization_rate or 0.0) / 100.0

    monthly_interest = mortgage_needed * rate_assumption / MONTHS_PER_YEAR
    monthly_amortization = mortgage_needed * amortization_rate / MONTHS_PER_YEAR
    monthly_operating_cost = float(scenario.monthly_fee_or_operating_cost or 0.0)
    monthly_insurance = float(scenario.monthly_insurance or 0.0)
    monthly_property_cost = float(scenario.monthly_property_cost_estimate or 0.0)
    monthly_total_cost = (
        monthly_interest
        + monthly_amortization
        + monthly_operating_cost
        + monthly_insurance
        + monthly_property_cost
    )

    return {
        "scenario_id": scenario.id,
        "household_id": scenario.household_id,
        "label": scenario.label,
        "purchase_price": float(scenario.purchase_price or 0.0),
        "down_payment": float(scenario.down_payment or 0.0),
        "mortgage_needed": mortgage_needed,
        "monthly_interest": round(monthly_interest, 2),
        "monthly_amortization": round(monthly_amortization, 2),
        "monthly_operating_cost": round(monthly_operating_cost, 2),
        "monthly_insurance": round(monthly_insurance, 2),
        "monthly_property_cost_estimate": round(monthly_property_cost, 2),
        "monthly_total_cost": round(monthly_total_cost, 2),
        "yearly_total_cost": round(monthly_total_cost * MONTHS_PER_YEAR, 2),
    }


def today_iso() -> date:
    return date.today()
