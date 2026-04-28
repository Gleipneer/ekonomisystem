"""
Bank-ready PDF export for household economics.

Generates a professional, Swedish-language PDF suitable for presenting
to a bank officer when applying for a mortgage or similar evaluation.
Uses only real deterministic data from the household — no fabricated numbers.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

from . import calculations, models
from sqlalchemy.orm import Session


MARGIN = 20 * mm
BRAND_DARK = colors.HexColor("#1a1a2e")
BRAND_ACCENT = colors.HexColor("#16213e")
BRAND_LIGHT = colors.HexColor("#f5f5f7")
BRAND_GREEN = colors.HexColor("#22c55e")
BRAND_MUTED = colors.HexColor("#6b7280")
TABLE_HEADER_BG = colors.HexColor("#e8e8ee")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PDFTitle", parent=base["Title"],
            fontSize=22, leading=28, textColor=BRAND_DARK,
            spaceAfter=4 * mm,
        ),
        "subtitle": ParagraphStyle(
            "PDFSubtitle", parent=base["Normal"],
            fontSize=11, leading=14, textColor=BRAND_MUTED,
            spaceAfter=8 * mm,
        ),
        "h2": ParagraphStyle(
            "PDFH2", parent=base["Heading2"],
            fontSize=14, leading=18, textColor=BRAND_DARK,
            spaceBefore=8 * mm, spaceAfter=3 * mm,
        ),
        "h3": ParagraphStyle(
            "PDFH3", parent=base["Heading3"],
            fontSize=11, leading=14, textColor=BRAND_ACCENT,
            spaceBefore=4 * mm, spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "PDFBody", parent=base["Normal"],
            fontSize=10, leading=13, textColor=BRAND_DARK,
        ),
        "muted": ParagraphStyle(
            "PDFMuted", parent=base["Normal"],
            fontSize=9, leading=12, textColor=BRAND_MUTED,
        ),
        "footer": ParagraphStyle(
            "PDFFooter", parent=base["Normal"],
            fontSize=8, leading=10, textColor=BRAND_MUTED,
        ),
    }


def _sek(value: float | None) -> str:
    if value is None:
        return "–"
    formatted = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} kr"


def _pct(value: float | None) -> str:
    if value is None:
        return "–"
    return f"{value:.1f} %".replace(".", ",")


def _table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), BRAND_DARK),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, BRAND_MUTED),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, BRAND_MUTED),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
    ])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(style)
    return t


def _summary_kv(data: list[tuple[str, str]], col_widths: list[float] | None = None) -> Table:
    style = TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), BRAND_MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), BRAND_DARK),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, BRAND_MUTED),
    ])
    t = Table(data, colWidths=col_widths or [90 * mm, 70 * mm])
    t.setStyle(style)
    return t


def generate_bank_pdf(db: Session, household_id: int) -> bytes:
    """Generate a bank-ready PDF for the given household. Returns PDF bytes."""
    records = calculations.load_household_records(db, household_id)
    summary = calculations.build_household_summary(records, household_id)
    household = records["households"][0] if records["households"] else {}

    housing_scenario = (
        db.query(models.HousingScenario)
        .filter_by(household_id=household_id)
        .order_by(models.HousingScenario.id.desc())
        .first()
    )
    housing_eval = calculations.evaluate_housing_scenario(housing_scenario) if housing_scenario else None

    pending_drafts = sum(
        1 for d in records["extraction_drafts"] if d.get("status") == "pending_review"
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    s = _styles()
    story: list[Any] = []
    page_width = A4[0] - 2 * MARGIN

    story.append(Paragraph("Hushållsekonomi – Bankkalkyl", s["title"]))
    story.append(Paragraph(
        f"{household.get('name', 'Hushåll')} · {date.today().isoformat()} · Valuta: {household.get('currency', 'SEK')}",
        s["subtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_MUTED, spaceAfter=4 * mm))

    story.append(Paragraph("Personer", s["h2"]))
    person_rows = [["Namn", "Roll", "Status"]]
    for p in records["persons"]:
        role_label = {"self": "Huvudperson", "partner": "Partner", "child": "Barn"}.get(p.get("role", ""), p.get("role", ""))
        person_rows.append([p.get("name", "–"), role_label, "Aktiv" if p.get("active") else "Inaktiv"])
    if len(person_rows) > 1:
        story.append(_table(person_rows, [70 * mm, 50 * mm, 40 * mm]))
    else:
        story.append(Paragraph("Inga personer registrerade.", s["muted"]))

    story.append(Paragraph("Inkomster", s["h2"]))
    income_rows = [["Källa", "Person", "Netto/mån", "Brutto/mån"]]
    for inc in records["income_sources"]:
        person_name = next((p.get("name", "–") for p in records["persons"] if p.get("id") == inc.get("person_id")), "–")
        net_monthly = calculations.amount_to_monthly(inc.get("net_amount"), inc.get("frequency"))
        gross_monthly = calculations.amount_to_monthly(inc.get("gross_amount"), inc.get("frequency"))
        income_rows.append([
            inc.get("source", inc.get("type", "–")),
            person_name,
            _sek(net_monthly) if inc.get("net_amount") else "–",
            _sek(gross_monthly) if inc.get("gross_amount") else "–",
        ])
    if len(income_rows) > 1:
        story.append(_table(income_rows, [55 * mm, 35 * mm, 35 * mm, 35 * mm]))
    story.append(Spacer(1, 2 * mm))
    story.append(_summary_kv([
        ("Total inkomst / månad", _sek(summary["monthly_income"])),
        ("  varav netto", _sek(summary["monthly_income_net"])),
        ("  varav brutto (ej skatteberäknad)", _sek(summary["monthly_income_gross_only"])),
    ]))

    story.append(Paragraph("Fasta utgifter", s["h2"]))

    if records["recurring_costs"]:
        story.append(Paragraph("Återkommande kostnader", s["h3"]))
        cost_rows = [["Kategori", "Leverantör", "Belopp/mån"]]
        for c in records["recurring_costs"]:
            monthly = calculations.amount_to_monthly(c.get("amount"), c.get("frequency"))
            cost_rows.append([c.get("category", "–"), c.get("vendor", "–"), _sek(monthly)])
        story.append(_table(cost_rows, [50 * mm, 60 * mm, 50 * mm]))

    if records["subscription_contracts"]:
        story.append(Paragraph("Abonnemang och avtal", s["h3"]))
        sub_rows = [["Leverantör", "Produkt", "Kostnad/mån"]]
        for sub in records["subscription_contracts"]:
            monthly = calculations.amount_to_monthly(sub.get("current_monthly_cost"), sub.get("billing_frequency"))
            sub_rows.append([sub.get("provider", "–"), sub.get("product_name", "–"), _sek(monthly)])
        story.append(_table(sub_rows, [55 * mm, 55 * mm, 50 * mm]))

    if records["insurance_policies"]:
        story.append(Paragraph("Försäkringar", s["h3"]))
        ins_rows = [["Typ", "Leverantör", "Premie/mån"]]
        for ins in records["insurance_policies"]:
            ins_rows.append([ins.get("type", "–"), ins.get("provider", "–"), _sek(ins.get("premium_monthly"))])
        story.append(_table(ins_rows, [50 * mm, 60 * mm, 50 * mm]))

    story.append(Spacer(1, 2 * mm))
    story.append(_summary_kv([
        ("Återkommande kostnader / mån", _sek(summary["monthly_recurring_costs"])),
        ("Abonnemang / mån", _sek(summary["monthly_subscriptions"])),
        ("Försäkringar / mån", _sek(summary["monthly_insurance"])),
        ("Fordonskostnader / mån", _sek(summary["monthly_vehicle_costs"])),
        ("Totala fasta utgifter / mån", _sek(summary["monthly_total_expenses"])),
    ]))

    if records["loans"]:
        story.append(Paragraph("Lån och skulder", s["h2"]))
        loan_rows = [["Långivare", "Syfte", "Betalning/mån", "Kvar skuld"]]
        for loan in records["loans"]:
            monthly = calculations.estimate_loan_monthly_payment(loan)
            loan_rows.append([
                loan.get("lender", "–"),
                loan.get("purpose", "–"),
                _sek(monthly),
                _sek(loan.get("current_balance")),
            ])
        story.append(_table(loan_rows, [40 * mm, 40 * mm, 40 * mm, 40 * mm]))
        story.append(Spacer(1, 2 * mm))
        story.append(_summary_kv([
            ("Totala lånekostnader / mån", _sek(summary["monthly_loan_payments"])),
            ("Total skuld", _sek(summary["loan_balance_total"])),
        ]))

    story.append(Paragraph("Kassaflöde", s["h2"]))
    story.append(_summary_kv([
        ("Inkomst / månad", _sek(summary["monthly_income"])),
        ("Utgifter / månad", _sek(summary["monthly_total_expenses"])),
        ("Kassaflöde / månad", _sek(summary["monthly_net_cashflow"])),
        ("Kassaflöde / år", _sek(summary["yearly_net_cashflow"])),
    ]))

    if housing_eval:
        story.append(Paragraph("Boendekalkyl", s["h2"]))
        story.append(Paragraph(f"Scenario: {housing_eval.get('label', '–')}", s["muted"]))
        story.append(Spacer(1, 2 * mm))
        story.append(_summary_kv([
            ("Köpeskilling", _sek(housing_eval.get("purchase_price"))),
            ("Kontantinsats", _sek(housing_eval.get("down_payment"))),
            ("Lånebehov", _sek(housing_eval.get("mortgage_needed"))),
            ("Ränta / mån", _sek(housing_eval.get("monthly_interest"))),
            ("Amortering / mån", _sek(housing_eval.get("monthly_amortization"))),
            ("Drift / mån", _sek(housing_eval.get("monthly_operating_cost"))),
            ("Försäkring / mån", _sek(housing_eval.get("monthly_insurance"))),
            ("Total boendekostnad / mån", _sek(housing_eval.get("monthly_total_cost"))),
        ]))
        margin_after = summary["monthly_net_cashflow"] - housing_eval.get("monthly_total_cost", 0)
        story.append(Spacer(1, 2 * mm))
        story.append(_summary_kv([
            ("Marginal efter boende / mån", _sek(round(margin_after, 2))),
        ]))

    if records["assets"]:
        story.append(Paragraph("Tillgångar", s["h2"]))
        asset_rows = [["Typ", "Institution", "Marknadsvärde"]]
        for a in records["assets"]:
            asset_rows.append([a.get("type", "–"), a.get("institution", "–"), _sek(a.get("market_value"))])
        story.append(_table(asset_rows, [50 * mm, 60 * mm, 50 * mm]))
        story.append(Spacer(1, 2 * mm))
        story.append(_summary_kv([
            ("Tillgångar marknadsvärde", _sek(summary["asset_market_value"])),
            ("Nettovärde (tillgångar − skulder)", _sek(summary["net_worth_estimate"])),
        ]))

    risk_signals = summary.get("risk_signals", [])
    if risk_signals:
        story.append(Paragraph("Risksignaler", s["h2"]))
        for sig in risk_signals:
            prefix = {"critical": "⚠ KRITISK", "warning": "⚠ VARNING", "info": "ℹ"}.get(sig.get("severity"), "ℹ")
            story.append(Paragraph(f"{prefix}: {sig.get('message_sv', '')}", s["body"]))
        story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_MUTED, spaceAfter=3 * mm))
    story.append(Paragraph("Datakällor och osäkerhet", s["h3"]))
    source_notes = [
        "Alla belopp bygger på registrerad hushållsdata i systemet.",
        f"Antal registrerade poster: {summary['counts']['income_sources']} inkomster, "
        f"{summary['counts']['recurring_costs']} återkommande kostnader, "
        f"{summary['counts']['subscription_contracts']} abonnemang, "
        f"{summary['counts']['loans']} lån, "
        f"{summary['counts']['assets']} tillgångar.",
    ]
    if summary.get("gross_income_only_entries", 0) > 0:
        source_notes.append(
            f"⚠ {summary['gross_income_only_entries']} inkomstkälla(or) saknar nettolön och visas med bruttobelopp."
        )
    if pending_drafts > 0:
        source_notes.append(
            f"⚠ {pending_drafts} reviewutkast väntar på granskning och ingår inte i beräkningarna."
        )
    for note in source_notes:
        story.append(Paragraph(note, s["muted"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"Genererad {date.today().isoformat()} · Household Economics System · Alla belopp i SEK om inte annat anges",
        s["footer"],
    ))

    doc.build(story)
    return buf.getvalue()
