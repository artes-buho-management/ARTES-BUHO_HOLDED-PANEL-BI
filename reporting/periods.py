from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, Optional
from zoneinfo import ZoneInfo

ReportType = Literal["weekly", "monthly", "annual"]

_MONTHS_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


@dataclass(frozen=True)
class PeriodInfo:
    report_type: ReportType
    run_datetime: datetime
    period_start: date
    period_end: date
    timezone: str
    report_title: str
    period_label: str

    @property
    def subfolder_name(self) -> str:
        if self.report_type == "weekly":
            return "InformeSemanal"
        if self.report_type == "monthly":
            return "InformeMensual"
        return "InformeAnual"


def parse_run_datetime(
    run_datetime_str: Optional[str], timezone: str = "Europe/Madrid"
) -> datetime:
    tz = ZoneInfo(timezone)
    if not run_datetime_str:
        return datetime.now(tz)

    candidate = run_datetime_str.strip()
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
    ]
    parsed: Optional[datetime] = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(candidate, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValueError(
            f"Formato de fecha no valido: {run_datetime_str}. Usa YYYY-MM-DD HH:MM."
        )

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def build_period(report_type: ReportType, run_datetime: datetime) -> PeriodInfo:
    if report_type == "weekly":
        return _build_weekly(run_datetime)
    if report_type == "monthly":
        return _build_monthly(run_datetime)
    if report_type == "annual":
        return _build_annual(run_datetime)
    raise ValueError(f"Tipo de informe no soportado: {report_type}")


def _build_weekly(run_datetime: datetime) -> PeriodInfo:
    run_date = run_datetime.date()
    this_monday = run_date - timedelta(days=run_date.weekday())
    start = this_monday - timedelta(days=7)
    end = this_monday - timedelta(days=1)
    label = f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
    return PeriodInfo(
        report_type="weekly",
        run_datetime=run_datetime,
        period_start=start,
        period_end=end,
        timezone=_tz_name(run_datetime),
        report_title="Informe Semanal",
        period_label=label,
    )


def _build_monthly(run_datetime: datetime) -> PeriodInfo:
    run_date = run_datetime.date()
    first_day_this_month = run_date.replace(day=1)
    end = first_day_this_month - timedelta(days=1)
    start = end.replace(day=1)
    month_name = _MONTHS_ES[start.month]
    label = f"{month_name.capitalize()} {start.year}"
    return PeriodInfo(
        report_type="monthly",
        run_datetime=run_datetime,
        period_start=start,
        period_end=end,
        timezone=_tz_name(run_datetime),
        report_title="Informe Mensual",
        period_label=label,
    )


def _build_annual(run_datetime: datetime) -> PeriodInfo:
    run_date = run_datetime.date()
    year = run_date.year - 1
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    return PeriodInfo(
        report_type="annual",
        run_datetime=run_datetime,
        period_start=start,
        period_end=end,
        timezone=_tz_name(run_datetime),
        report_title="Informe Anual",
        period_label=str(year),
    )


def _tz_name(run_datetime: datetime) -> str:
    if run_datetime.tzinfo:
        return str(run_datetime.tzinfo)
    return "Europe/Madrid"

