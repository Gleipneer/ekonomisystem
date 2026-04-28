from __future__ import annotations

from .. import calculations
from .schemas import CycleStatus


def compute_cycle_status(records: dict, current_balance: float | None = None) -> CycleStatus:
    monthly_income = sum(
        calculations.amount_to_monthly(item.get("net_amount"), item.get("frequency"))
        for item in records.get("income_sources", [])
        if item.get("net_amount") is not None
    ) + sum(
        calculations.amount_to_monthly(item.get("gross_amount"), item.get("frequency"))
        for item in records.get("income_sources", [])
        if item.get("net_amount") is None and item.get("gross_amount") is not None
    )
    monthly_total_expenses = (
        sum(calculations.amount_to_monthly(item.get("amount"), item.get("frequency")) for item in records.get("recurring_costs", []))
        + sum(
            calculations.amount_to_monthly(item.get("current_monthly_cost"), item.get("billing_frequency"))
            for item in records.get("subscription_contracts", [])
        )
        + sum(float(item.get("premium_monthly") or 0.0) for item in records.get("insurance_policies", []))
        + sum(calculations.estimate_vehicle_monthly_cost(item) for item in records.get("vehicles", []))
        + sum(calculations.estimate_loan_monthly_payment(item) for item in records.get("loans", []))
    )
    monthly_net_cashflow = monthly_income - monthly_total_expenses
    status = "stable" if monthly_net_cashflow >= 0 else "at_risk"
    return CycleStatus(
        monthly_income=round(monthly_income, 2),
        monthly_total_expenses=round(monthly_total_expenses, 2),
        monthly_net_cashflow=round(monthly_net_cashflow, 2),
        current_balance=current_balance,
        status=status,
    )
