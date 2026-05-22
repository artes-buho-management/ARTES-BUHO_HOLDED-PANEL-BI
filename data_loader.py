from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Tuple

import gspread
import pandas as pd
import requests
from google.oauth2.service_account import Credentials

from config import Settings, get_service_account_info


@dataclass
class LoadResult:
    sheets: Dict[str, pd.DataFrame]
    source_type: str
    details: str


def load_google_sheets_data(settings: Settings) -> LoadResult:
    if settings.google_sheet_public_csv_url:
        df = _load_single_csv(settings.google_sheet_public_csv_url)
        return LoadResult(
            sheets={settings.preferred_worksheet or "datos": df},
            source_type="public_csv_url",
            details="Carga desde URL CSV publica configurada",
        )

    if settings.google_sheet_id:
        try:
            sheets = _load_from_public_xlsx_export(settings.google_sheet_id)
            if sheets:
                return LoadResult(
                    sheets=sheets,
                    source_type="public_xlsx_export",
                    details="Carga desde export publico XLSX de Google Sheets",
                )
        except Exception:
            pass

    if not settings.google_sheet_id:
        raise RuntimeError("Falta GOOGLE_SHEET_ID")

    sheets = _load_via_google_api(settings)
    return LoadResult(
        sheets=sheets,
        source_type="google_sheets_api",
        details="Carga via Google Sheets API con service account",
    )


def _load_single_csv(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=45)
    response.raise_for_status()
    return pd.read_csv(BytesIO(response.content))


def _load_from_public_xlsx_export(sheet_id: str) -> Dict[str, pd.DataFrame]:
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    response = requests.get(export_url, timeout=60)
    response.raise_for_status()

    data = pd.read_excel(BytesIO(response.content), sheet_name=None)
    out: Dict[str, pd.DataFrame] = {}
    for sheet_name, df in data.items():
        if df is None:
            continue
        clean = df.copy()
        clean.columns = [str(c).strip() for c in clean.columns]
        out[str(sheet_name).strip() or "Hoja"] = clean
    return out


def _load_via_google_api(settings: Settings) -> Dict[str, pd.DataFrame]:
    info = get_service_account_info(settings)
    if not info:
        raise RuntimeError(
            "No hay acceso publico al Sheet y faltan credenciales API (GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_APPLICATION_CREDENTIALS)."
        )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    credentials = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(credentials)
    workbook = gc.open_by_key(settings.google_sheet_id)

    out: Dict[str, pd.DataFrame] = {}
    for ws in workbook.worksheets():
        rows = ws.get_all_values()
        out[ws.title] = _rows_to_dataframe(rows)

    return out


def _rows_to_dataframe(rows: List[List[str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    header = rows[0]
    values = rows[1:] if len(rows) > 1 else []
    header = _make_unique_headers(header)
    return pd.DataFrame(values, columns=header)


def _make_unique_headers(headers: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    output: List[str] = []
    for idx, value in enumerate(headers):
        base = str(value).strip() or f"columna_{idx + 1}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        output.append(base if count == 0 else f"{base}_{count + 1}")
    return output
