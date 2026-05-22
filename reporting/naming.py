from __future__ import annotations

from reporting.periods import PeriodInfo


def build_report_filename(period: PeriodInfo) -> str:
    if period.report_type == "weekly":
        return f"{period.run_datetime.strftime('%y%m%d')}_InformeSemanal.pdf"
    if period.report_type == "monthly":
        return f"{period.period_start.strftime('%y%m')}_InformeMensual.pdf"
    if period.report_type == "annual":
        return f"{period.period_start.strftime('%Y')}_InformeAnual.pdf"
    raise ValueError(f"Tipo de informe no soportado: {period.report_type}")

