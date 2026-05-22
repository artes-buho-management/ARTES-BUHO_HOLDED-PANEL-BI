from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from config import Settings
from reporting.periods import PeriodInfo


@dataclass(frozen=True)
class EmailPreview:
    enabled: bool
    dry_run: bool
    report_type: str
    recipients: List[str]
    subject: str
    body: str
    attachment_path: str
    status: str


class EmailManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def prepare_preview(
        self,
        report_type: str,
        period: PeriodInfo,
        attachment_path: str,
        dry_run: bool = True,
    ) -> EmailPreview:
        recipients = self._recipients_for_type(report_type)
        subject = self._build_subject(report_type, period)
        body = self._build_body(report_type, period)

        if not Path(attachment_path).exists():
            status = "error_attachment_not_found"
        elif not self.settings.email_enabled:
            status = "disabled"
        elif dry_run:
            status = "dry_run_ready"
        else:
            status = "ready_not_sent"

        return EmailPreview(
            enabled=self.settings.email_enabled,
            dry_run=dry_run,
            report_type=report_type,
            recipients=recipients,
            subject=subject,
            body=body,
            attachment_path=attachment_path,
            status=status,
        )

    def _recipients_for_type(self, report_type: str) -> List[str]:
        raw = ""
        if report_type == "weekly":
            raw = self.settings.email_recipients_weekly
        elif report_type == "monthly":
            raw = self.settings.email_recipients_monthly
        elif report_type == "annual":
            raw = self.settings.email_recipients_annual
        recipients = [x.strip() for x in raw.split(",") if x.strip()]
        return recipients

    def _build_subject(self, report_type: str, period: PeriodInfo) -> str:
        type_label = {
            "weekly": "Informe Semanal",
            "monthly": "Informe Mensual",
            "annual": "Informe Anual",
        }.get(report_type, "Informe")
        return f"{self.settings.email_subject_prefix} {type_label} - {period.period_label}"

    def _build_body(self, report_type: str, period: PeriodInfo) -> str:
        type_label = {
            "weekly": "semanal",
            "monthly": "mensual",
            "annual": "anual",
        }.get(report_type, "periodico")
        return (
            f"Hola,\n\n"
            f"Adjuntamos el informe {type_label} de {self.settings.company_name}.\n"
            f"Periodo analizado: {period.period_label}\n"
            f"Generado: {period.run_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}\n\n"
            f"Sistema desarrollado por {self.settings.developer_name}.\n"
        )

