from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from .. import calculations
from .schemas import (
    AnalysisActionPrimitive,
    AnalysisAlert,
    AnalysisOutput,
    AnalysisPresentation,
    PresentationMetric,
    PresentationPrimitive,
)


def _format_currency(value: float) -> str:
    return f"{round(value):,} kr".replace(",", " ")


def build_analysis_output(
    db: Session,
    household_id: int,
    current_balance: float | None = None,
    *,
    as_of: date | None = None,
) -> AnalysisOutput:
    records = calculations.load_household_records(db, household_id)
    summary = calculations.build_household_summary(records, household_id)

    alerts = [
        AnalysisAlert(
            title=item.get("key", "signal"),
            message=item.get("message_sv", ""),
            severity=item.get("severity", "info"),
        )
        for item in summary.get("risk_signals", [])
    ]
    action_primitives = [
        AnalysisActionPrimitive(
            title="Granska review-kö",
            description="Hantera väntande dokumentutkast innan nya antaganden görs.",
        ),
        AnalysisActionPrimitive(
            title="Validera månadens fasta poster",
            description="Bekräfta återkommande kostnader och abonnemang innan apply.",
        ),
    ]
    presentation = AnalysisPresentation(
        headline_metrics=[
            PresentationMetric(
                label="Kassaflöde",
                value=_format_currency(float(summary.get("monthly_net_cashflow", 0.0))),
                tone="success" if float(summary.get("monthly_net_cashflow", 0.0)) >= 0 else "warning",
                detail=f"Inkomster {_format_currency(float(summary.get('monthly_income', 0.0)))}",
            ),
            PresentationMetric(
                label="Utgifter",
                value=_format_currency(float(summary.get("monthly_total_expenses", 0.0))),
                tone="neutral",
                detail="Deterministiskt beräknat",
            ),
        ],
        summary_primitives=[
            PresentationPrimitive(
                title="Netto efter fasta poster",
                value=_format_currency(float(summary.get("monthly_net_cashflow", 0.0))),
                tone="neutral",
            ),
            PresentationPrimitive(
                title="Aktiva lån",
                value=str(int(summary.get("counts", {}).get("loans", 0))),
                tone="neutral",
            ),
        ],
    )

    return AnalysisOutput(
        household_id=household_id,
        as_of=as_of,
        monthly_income=float(summary.get("monthly_income", 0.0)),
        monthly_total_expenses=float(summary.get("monthly_total_expenses", 0.0)),
        monthly_net_cashflow=float(summary.get("monthly_net_cashflow", 0.0)),
        alerts=alerts,
        action_primitives=action_primitives,
        presentation=presentation,
    )
