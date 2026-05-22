from __future__ import annotations

from pathlib import Path

from config import get_settings
from reporting.email_manager import EmailManager
from reporting.periods import build_period, parse_run_datetime


def test_email_dry_run_disabled_by_default(tmp_path: Path):
    settings = get_settings()
    period = build_period("weekly", parse_run_datetime("2026-04-06 08:00", settings.timezone))

    attachment = tmp_path / "demo.pdf"
    attachment.write_bytes(b"%PDF-1.4 demo")

    manager = EmailManager(settings)
    preview = manager.prepare_preview(
        report_type="weekly",
        period=period,
        attachment_path=str(attachment),
        dry_run=True,
    )
    assert preview.enabled is False
    assert preview.dry_run is True
    assert preview.status == "disabled"
    assert "Informe Semanal" in preview.subject

