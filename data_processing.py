from __future__ import annotations

import re
import unicodedata
import warnings
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd


@dataclass
class ProcessedData:
    dataframe: pd.DataFrame
    column_map: Dict[str, str]
    inferred_types: Dict[str, str]
    semantic_roles: Dict[str, str]
    quality_report: Dict[str, object]


def clean_and_prepare(df: pd.DataFrame) -> ProcessedData:
    original_rows = len(df)
    original_cols = len(df.columns)

    work = df.copy()
    work.columns = [str(c).strip() for c in work.columns]
    work = work.replace(r"^\s*$", pd.NA, regex=True)

    empty_rows_before = int(work.isna().all(axis=1).sum())
    empty_cols_before = int(work.isna().all(axis=0).sum())

    work = work.dropna(how="all", axis=0).dropna(how="all", axis=1)
    work = work.loc[:, ~work.columns.duplicated()]
    work = work.drop_duplicates()

    normalized_columns, column_map = _normalize_columns(list(work.columns))
    work.columns = normalized_columns

    inferred_types: Dict[str, str] = {}
    semantic_roles: Dict[str, str] = {}
    converted = pd.DataFrame(index=work.index)

    for col in work.columns:
        series = work[col]
        prepared_series, inferred_type = _infer_and_cast(series, col)
        converted[col] = prepared_series
        inferred_types[col] = inferred_type
        semantic_roles[col] = _infer_semantic_role(col, prepared_series, inferred_type)

    quality_report = {
        "filas_entrada": int(original_rows),
        "columnas_entrada": int(original_cols),
        "filas_salida": int(len(converted)),
        "columnas_salida": int(len(converted.columns)),
        "filas_vacias_eliminadas": int(empty_rows_before),
        "columnas_vacias_eliminadas": int(empty_cols_before),
        "columnas_originales": list(column_map.keys()),
        "columnas_normalizadas": list(column_map.values()),
    }

    return ProcessedData(
        dataframe=converted,
        column_map=column_map,
        inferred_types=inferred_types,
        semantic_roles=semantic_roles,
        quality_report=quality_report,
    )


def _normalize_columns(columns: List[str]) -> Tuple[List[str], Dict[str, str]]:
    normalized: List[str] = []
    mapping: Dict[str, str] = {}
    seen: Dict[str, int] = {}

    for idx, original in enumerate(columns):
        base = _slugify(original) or f"columna_{idx + 1}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        final_name = base if count == 0 else f"{base}_{count + 1}"
        normalized.append(final_name)
        mapping[original] = final_name

    return normalized, mapping


def _slugify(value: str) -> str:
    text = str(value).strip().lower()
    text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _infer_and_cast(series: pd.Series, col_name: str) -> Tuple[pd.Series, str]:
    raw = series.copy()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        dt_try = pd.to_datetime(raw, errors="coerce", dayfirst=True)
    dt_ratio = float(dt_try.notna().mean()) if len(raw) else 0.0

    numeric_try = _parse_numeric_series(raw)
    numeric_ratio = float(numeric_try.notna().mean()) if len(raw) else 0.0

    if dt_ratio >= 0.85 and dt_ratio >= numeric_ratio:
        return dt_try, "datetime"

    if numeric_ratio >= 0.85:
        return numeric_try, "numeric"

    as_text = raw.astype("string").str.strip()
    return as_text, "string"


def _parse_numeric_series(series: pd.Series) -> pd.Series:
    txt = series.astype("string").fillna("").str.strip()
    txt = txt.str.replace(r"[€$£]", "", regex=True)
    txt = txt.str.replace(r"\s+", "", regex=True)
    txt = txt.str.replace("%", "", regex=False)

    has_comma = txt.str.contains(",", regex=False)
    has_dot = txt.str.contains(".", regex=False)

    both = has_comma & has_dot
    comma_only = has_comma & ~has_dot

    txt = txt.where(~both, txt.str.replace(".", "", regex=False))
    txt = txt.where(~both, txt.str.replace(",", ".", regex=False))
    txt = txt.where(~comma_only, txt.str.replace(",", ".", regex=False))

    txt = txt.str.replace(r"[^0-9\.-]", "", regex=True)
    parsed = pd.to_numeric(txt, errors="coerce")
    return parsed


def _infer_semantic_role(col_name: str, series: pd.Series, inferred_type: str) -> str:
    col = col_name.lower()
    non_null = int(series.notna().sum())
    nunique = int(series.nunique(dropna=True))
    unique_ratio = (nunique / non_null) if non_null > 0 else 0.0

    if inferred_type == "datetime":
        return "fecha"

    if inferred_type == "numeric":
        if _contains_any(col, ["pct", "porcentaje", "ratio", "tasa", "conversion"]):
            return "porcentaje"
        if _contains_any(
            col,
            [
                "importe",
                "monto",
                "amount",
                "ingreso",
                "revenue",
                "facturacion",
                "coste",
                "costo",
                "margen",
                "precio",
                "beneficio",
            ],
        ):
            return "importe_monetario"
        return "metrica_numerica"

    if _contains_any(col, ["estado", "status", "fase", "etapa"]):
        return "estado"
    if _contains_any(col, ["pais", "country", "region", "provincia", "ciudad", "city", "zona"]):
        return "geografia"
    if _contains_any(col, ["canal", "channel", "medio"]):
        return "canal"
    if _contains_any(col, ["producto", "sku", "item", "servicio"]):
        return "producto"
    if _contains_any(col, ["cliente", "customer", "cuenta", "empresa"]):
        return "cliente"
    if _contains_any(col, ["comercial", "vendedor", "sales", "owner", "agente"]):
        return "comercial"
    if _contains_any(col, ["origen", "source", "utm"]):
        return "origen"
    if _contains_any(col, ["id", "codigo", "uuid", "dni", "nif", "email", "telefono"]) or (
        unique_ratio > 0.95 and non_null >= 20
    ):
        return "identificador"

    avg_len = float(series.dropna().astype(str).str.len().mean()) if non_null else 0.0
    if nunique <= 30:
        return "categoria"
    if avg_len >= 45:
        return "texto_libre"
    return "categoria"


def _contains_any(text: str, terms: List[str]) -> bool:
    return any(term in text for term in terms)


def find_relevant_columns(
    df: pd.DataFrame, semantic_roles: Dict[str, str]
) -> Dict[str, List[str]]:
    date_cols = [c for c, r in semantic_roles.items() if r == "fecha"]
    metric_cols = [
        c
        for c, r in semantic_roles.items()
        if r in {"metrica_numerica", "importe_monetario", "porcentaje"}
    ]
    category_cols = [
        c
        for c, r in semantic_roles.items()
        if r
        in {
            "categoria",
            "estado",
            "geografia",
            "canal",
            "producto",
            "cliente",
            "comercial",
            "origen",
        }
        and df[c].nunique(dropna=True) <= 100
    ]
    return {"date_cols": date_cols, "metric_cols": metric_cols, "category_cols": category_cols}
