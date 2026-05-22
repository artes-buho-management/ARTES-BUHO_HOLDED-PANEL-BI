from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from config import Settings
from reporting.drive_manager import DriveManager, UploadResult
from reporting.email_manager import EmailManager
from reporting.naming import build_report_filename
from reporting.pdf_builder import build_report_pdf
from reporting.periods import PeriodInfo, ReportType, build_period, parse_run_datetime
from shared.analysis_service import (
    choose_sheet_name,
    execute_analysis,
    load_source_sheets,
    prepare_sheet,
)


@dataclass
class ReportGenerationResult:
    report_type: str
    period_label: str
    run_datetime: str
    local_pdf_path: str
    upload_status: str
    upload_message: str
    drive_link: str
    email_status: str
    email_subject: str
    selected_sheet: str


ANOMALY_THRESHOLD_BY_REPORT = {
    "weekly": 35.0,
    "monthly": 45.0,
    "annual": 45.0,
}


def generate_report(
    report_type: ReportType,
    settings: Settings,
    run_datetime_str: Optional[str] = None,
    sheet_name: str = "",
    overwrite: bool = False,
    dry_run: bool = False,
) -> ReportGenerationResult:
    run_dt = parse_run_datetime(run_datetime_str, settings.timezone)
    period = build_period(report_type, run_dt)
    load_result, selected_sheet, analysis = _prepare_report_analysis(
        report_type=report_type,
        period=period,
        settings=settings,
        sheet_name=sheet_name,
    )

    filename = build_report_filename(period)
    local_path = _local_output_path(settings, period, filename)
    local_pdf_path = build_report_pdf(
        output_path=str(local_path),
        report_type=report_type,
        period=period,
        analysis=analysis,
        settings=settings,
        source_sheet_name=selected_sheet,
        source_detail=load_result.details,
    )

    upload_result = _upload_report_if_possible(
        settings=settings,
        period=period,
        local_pdf_path=local_pdf_path,
        filename=filename,
        overwrite=overwrite,
        dry_run=dry_run,
    )

    email_preview = EmailManager(settings).prepare_preview(
        report_type=report_type,
        period=period,
        attachment_path=local_pdf_path,
        dry_run=True,
    )

    return ReportGenerationResult(
        report_type=report_type,
        period_label=period.period_label,
        run_datetime=period.run_datetime.strftime("%Y-%m-%d %H:%M:%S %Z"),
        local_pdf_path=local_pdf_path,
        upload_status=upload_result.status,
        upload_message=upload_result.message,
        drive_link=upload_result.web_view_link or "",
        email_status=email_preview.status,
        email_subject=email_preview.subject,
        selected_sheet=selected_sheet,
    )


def _prepare_report_analysis(
    report_type: ReportType,
    period: PeriodInfo,
    settings: Settings,
    sheet_name: str,
):
    load_result = load_source_sheets(settings)
    selected_sheet = choose_sheet_name(load_result, sheet_name or settings.preferred_worksheet)
    processed = prepare_sheet(load_result.sheets[selected_sheet])
    analysis = execute_analysis(
        processed=processed,
        date_range=_build_date_range(period),
        category_filters={},
        forced_metric=None,
        anomaly_threshold_pct=ANOMALY_THRESHOLD_BY_REPORT[report_type],
    )
    return load_result, selected_sheet, analysis


def _build_date_range(period: PeriodInfo):
    start = pd.Timestamp(period.period_start)
    end = pd.Timestamp(period.period_end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return start, end


def _local_output_path(settings: Settings, period: PeriodInfo, filename: str) -> Path:
    base = Path(settings.reports_output_dir)
    folder = base / period.subfolder_name
    folder.mkdir(parents=True, exist_ok=True)
    return folder / filename


def _upload_report_if_possible(
    settings: Settings,
    period: PeriodInfo,
    local_pdf_path: str,
    filename: str,
    overwrite: bool,
    dry_run: bool,
) -> UploadResult:
    if dry_run:
        return UploadResult(
            status="dry_run",
            file_id=None,
            web_view_link=None,
            message="Dry-run activo: PDF generado localmente sin subir a Drive.",
        )

    if not settings.google_sheet_id and not settings.google_drive_folder_id:
        return UploadResult(
            status="not_configured",
            file_id=None,
            web_view_link=None,
            message="Falta GOOGLE_SHEET_ID o GOOGLE_DRIVE_FOLDER_ID para resolver carpeta de destino en Drive.",
        )

    try:
        drive_manager = DriveManager.from_settings(settings)
    except Exception as exc:
        return UploadResult(
            status="not_configured",
            file_id=None,
            web_view_link=None,
            message=f"Drive no configurado: {exc}",
        )

    folders = drive_manager.ensure_report_structure(
        sheet_id=settings.google_sheet_id,
        forced_parent_id=settings.google_drive_folder_id,
    )
    target_folder = folders.target_folder(period.report_type)
    return drive_manager.upload_pdf(
        local_pdf_path=local_pdf_path,
        target_folder_id=target_folder,
        filename=filename,
        overwrite=overwrite,
    )
