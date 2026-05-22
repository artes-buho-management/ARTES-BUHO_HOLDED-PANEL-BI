from __future__ import annotations

from reporting.naming import build_report_filename
from reporting.periods import build_period, parse_run_datetime


def test_weekly_name_example():
    run_dt = parse_run_datetime("2026-04-06 08:00", "Europe/Madrid")
    period = build_period("weekly", run_dt)
    assert build_report_filename(period) == "260406_InformeSemanal.pdf"


def test_monthly_name_example():
    run_dt = parse_run_datetime("2026-04-01 08:00", "Europe/Madrid")
    period = build_period("monthly", run_dt)
    assert build_report_filename(period) == "2603_InformeMensual.pdf"


def test_annual_name_example():
    run_dt = parse_run_datetime("2027-01-01 08:00", "Europe/Madrid")
    period = build_period("annual", run_dt)
    assert build_report_filename(period) == "2026_InformeAnual.pdf"

