from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


def _read_streamlit_secrets() -> Dict[str, Any]:
    try:
        import streamlit as st  # type: ignore

        return dict(st.secrets)
    except Exception:
        return {}


def _read_setting(key: str, default: str = "") -> str:
    env_value = os.getenv(key)
    if env_value is not None and str(env_value).strip():
        return str(env_value).strip()

    secrets = _read_streamlit_secrets()
    secret_value = secrets.get(key)
    if secret_value is None:
        return default
    return str(secret_value).strip() or default


def _read_bool_setting(key: str, default: bool = False) -> bool:
    raw = _read_setting(key, "")
    if not raw:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "si", "on"}


@dataclass(frozen=True)
class Settings:
    google_sheet_id: str
    google_sheet_public_csv_url: str
    preferred_worksheet: str
    panel_name: str
    panel_description: str
    streamlit_public_url: str
    timezone: str
    google_service_account_json: str
    google_application_credentials: str
    google_drive_folder_id: str
    company_name: str
    developer_name: str
    logo_path: str
    brand_red: str
    brand_yellow: str
    brand_white: str
    reports_output_dir: str
    email_enabled: bool
    email_sender: str
    email_recipients_weekly: str
    email_recipients_monthly: str
    email_recipients_annual: str
    email_subject_prefix: str


def get_settings() -> Settings:
    return Settings(
        google_sheet_id=_read_setting("GOOGLE_SHEET_ID", ""),
        google_sheet_public_csv_url=_read_setting("GOOGLE_SHEET_PUBLIC_CSV_URL", ""),
        preferred_worksheet=_read_setting("GOOGLE_SHEET_WORKSHEET", ""),
        panel_name=_read_setting("PANEL_NAME", "Panel Ejecutivo"),
        panel_description=_read_setting(
            "PANEL_DESCRIPTION", "Panel automatico para toma de decisiones"
        ),
        streamlit_public_url=_read_setting("STREAMLIT_PUBLIC_URL", ""),
        timezone=_read_setting("TIMEZONE", "Europe/Madrid"),
        google_service_account_json=_read_setting("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
        google_application_credentials=_read_setting("GOOGLE_APPLICATION_CREDENTIALS", ""),
        google_drive_folder_id=_read_setting("GOOGLE_DRIVE_FOLDER_ID", ""),
        company_name=_read_setting("COMPANY_NAME", "Artes Buho"),
        developer_name=_read_setting("DEVELOPER_NAME", "RUBEN COTON"),
        logo_path=_read_setting("LOGO_PATH", "assets/logo_artes_buho.png"),
        brand_red=_read_setting("BRAND_RED", "#D7263D"),
        brand_yellow=_read_setting("BRAND_YELLOW", "#FFC857"),
        brand_white=_read_setting("BRAND_WHITE", "#FFFFFF"),
        reports_output_dir=_read_setting("REPORTS_OUTPUT_DIR", "reports_output"),
        email_enabled=_read_bool_setting("EMAIL_ENABLED", False),
        email_sender=_read_setting("EMAIL_SENDER", ""),
        email_recipients_weekly=_read_setting("EMAIL_RECIPIENTS_WEEKLY", ""),
        email_recipients_monthly=_read_setting("EMAIL_RECIPIENTS_MONTHLY", ""),
        email_recipients_annual=_read_setting("EMAIL_RECIPIENTS_ANNUAL", ""),
        email_subject_prefix=_read_setting("EMAIL_SUBJECT_PREFIX", "[Artes Buho]"),
    )


def get_service_account_info(settings: Settings) -> Optional[Dict[str, Any]]:
    raw = settings.google_service_account_json.strip()
    if raw:
        return json.loads(raw)

    path = settings.google_application_credentials.strip()
    if not path:
        return None
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No existe GOOGLE_APPLICATION_CREDENTIALS en ruta: {path}"
        )
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
