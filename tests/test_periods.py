from __future__ import annotations

from reporting.periods import build_period, parse_run_datetime


def test_weekly_period_example():
    run_dt = parse_run_datetime("2026-04-06 08:00", "Europe/Madrid")
    period = build_period("weekly", run_dt)
    assert period.period_start.isoformat() == "2026-03-30"
    assert period.period_end.isoformat() == "2026-04-05"


def test_monthly_period_example():
    run_dt = parse_run_datetime("2026-04-01 08:00", "Europe/Madrid")
    period = build_period("monthly", run_dt)
    assert period.period_start.isoformat() == "2026-03-01"
    assert period.period_end.isoformat() == "2026-03-31"


def test_annual_period_example():
    run_dt = parse_run_datetime("2027-01-01 08:00", "Europe/Madrid")
    period = build_period("annual", run_dt)
    assert period.period_start.isoformat() == "2026-01-01"
    assert period.period_end.isoformat() == "2026-12-31"

