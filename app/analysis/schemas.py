from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class PlannedPurchaseItem(BaseModel):
    id: int | None = None
    title: str
    category: str | None = None
    estimated_amount: float
    priority: str = "optional"
    due_window: str | None = None
    status: str = "planned"


class AnalysisAlert(BaseModel):
    title: str
    message: str
    severity: Literal["info", "warning", "critical"] = "info"


class AnalysisActionPrimitive(BaseModel):
    title: str
    description: str


class PresentationMetric(BaseModel):
    label: str
    value: str
    tone: Literal["success", "neutral", "warning", "critical"] = "neutral"
    detail: str | None = None


class PresentationPrimitive(BaseModel):
    title: str
    value: str
    tone: Literal["success", "neutral", "warning", "critical"] = "neutral"
    detail: str | None = None


class AnalysisPresentation(BaseModel):
    headline_metrics: list[PresentationMetric] = Field(default_factory=list)
    summary_primitives: list[PresentationPrimitive] = Field(default_factory=list)


class AnalysisOutput(BaseModel):
    household_id: int
    as_of: date | None = None
    monthly_income: float = 0.0
    monthly_total_expenses: float = 0.0
    monthly_net_cashflow: float = 0.0
    alerts: list[AnalysisAlert] = Field(default_factory=list)
    action_primitives: list[AnalysisActionPrimitive] = Field(default_factory=list)
    presentation: AnalysisPresentation = Field(default_factory=AnalysisPresentation)


class CycleStatus(BaseModel):
    monthly_income: float = 0.0
    monthly_total_expenses: float = 0.0
    monthly_net_cashflow: float = 0.0
    current_balance: float | None = None
    status: str = "stable"
