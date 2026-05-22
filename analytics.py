from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class KPIBundle:
    total_rows: int
    principal_metric: Optional[str]
    principal_total: Optional[float]
    principal_avg: Optional[float]
    principal_median: Optional[float]
    previous_period_total: Optional[float]
    delta_vs_previous: Optional[float]


def choose_primary_sheet(sheets: Dict[str, pd.DataFrame]) -> str:
    if not sheets:
        raise RuntimeError("No hay hojas disponibles.")

    best_name = list(sheets.keys())[0]
    best_score = -1.0
    for name, df in sheets.items():
        score = _score_sheet(df)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name


def _score_sheet(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 0.0

    rows = len(df)
    cols = len(df.columns)
    non_empty_ratio = float(df.notna().mean().mean()) if rows and cols else 0.0
    score = rows * 0.5 + cols * 3 + non_empty_ratio * 100
    return float(score)


def apply_filters(
    df: pd.DataFrame,
    date_col: Optional[str],
    date_range: Optional[Tuple[pd.Timestamp, pd.Timestamp]],
    category_filters: Dict[str, List[str]],
) -> pd.DataFrame:
    out = df.copy()

    if date_col and date_col in out.columns and date_range:
        start_date, end_date = date_range
        out = out[(out[date_col] >= start_date) & (out[date_col] <= end_date)]

    for col, selected in category_filters.items():
        if not selected or col not in out.columns:
            continue
        out = out[out[col].astype(str).isin(selected)]

    return out


def compute_kpis(df: pd.DataFrame, metric_cols: List[str], date_col: Optional[str]) -> KPIBundle:
    metric = metric_cols[0] if metric_cols else None
    if not metric or metric not in df.columns:
        return KPIBundle(
            total_rows=int(len(df)),
            principal_metric=None,
            principal_total=None,
            principal_avg=None,
            principal_median=None,
            previous_period_total=None,
            delta_vs_previous=None,
        )

    series = pd.to_numeric(df[metric], errors="coerce")
    total = float(series.sum()) if series.notna().any() else None
    avg = float(series.mean()) if series.notna().any() else None
    median = float(series.median()) if series.notna().any() else None

    previous_total = None
    delta = None
    if date_col and date_col in df.columns and df[date_col].notna().any():
        previous_total, delta = _compute_previous_period_delta(df, date_col, metric)

    return KPIBundle(
        total_rows=int(len(df)),
        principal_metric=metric,
        principal_total=total,
        principal_avg=avg,
        principal_median=median,
        previous_period_total=previous_total,
        delta_vs_previous=delta,
    )


def _compute_previous_period_delta(
    df: pd.DataFrame, date_col: str, metric: str
) -> Tuple[Optional[float], Optional[float]]:
    temp = df[[date_col, metric]].copy()
    temp = temp.dropna(subset=[date_col])
    if temp.empty:
        return None, None

    min_date = temp[date_col].min()
    max_date = temp[date_col].max()
    days = max(1, int((max_date - min_date).days) + 1)

    current_start = max_date - pd.Timedelta(days=days - 1)
    prev_end = current_start - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=days - 1)

    current_total = (
        pd.to_numeric(temp.loc[temp[date_col] >= current_start, metric], errors="coerce").sum()
    )
    prev_total = pd.to_numeric(
        temp.loc[(temp[date_col] >= prev_start) & (temp[date_col] <= prev_end), metric],
        errors="coerce",
    ).sum()

    if prev_total == 0:
        return float(prev_total), None
    delta_pct = ((current_total - prev_total) / abs(prev_total)) * 100
    return float(prev_total), float(delta_pct)


def build_time_series(
    df: pd.DataFrame, date_col: Optional[str], metric_col: Optional[str]
) -> Optional[pd.DataFrame]:
    if not date_col or not metric_col or date_col not in df.columns or metric_col not in df.columns:
        return None
    temp = df[[date_col, metric_col]].dropna(subset=[date_col]).copy()
    if temp.empty:
        return None

    temp[metric_col] = pd.to_numeric(temp[metric_col], errors="coerce")
    temp = temp.dropna(subset=[metric_col])
    if temp.empty:
        return None

    span_days = max(1, int((temp[date_col].max() - temp[date_col].min()).days) + 1)
    if span_days > 365 * 2:
        freq = "M"
    elif span_days > 120:
        freq = "W"
    else:
        freq = "D"

    grouped = (
        temp.set_index(date_col)
        .resample(freq)[metric_col]
        .sum()
        .rename("valor")
        .reset_index()
    )
    grouped["variacion_pct"] = grouped["valor"].pct_change() * 100
    return grouped


def build_category_breakdown(
    df: pd.DataFrame, category_cols: List[str], metric_col: Optional[str]
) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    if not metric_col or metric_col not in df.columns:
        return out

    metric = pd.to_numeric(df[metric_col], errors="coerce")
    base = df.copy()
    base[metric_col] = metric
    base = base.dropna(subset=[metric_col])
    if base.empty:
        return out

    for col in category_cols[:4]:
        if col not in base.columns:
            continue
        grouped = (
            base.groupby(col, dropna=False)[metric_col]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
        )
        if grouped.empty:
            continue
        out[col] = grouped.head(15)
    return out


def detect_simple_anomalies(
    series_df: Optional[pd.DataFrame], threshold_pct: float = 40.0
) -> List[str]:
    if series_df is None or series_df.empty or "variacion_pct" not in series_df.columns:
        return []
    out: List[str] = []
    recent = series_df.tail(6)
    for _, row in recent.iterrows():
        change = row.get("variacion_pct")
        if pd.isna(change):
            continue
        if float(change) <= -abs(threshold_pct):
            out.append(
                f"Caida brusca detectada: {float(change):.1f}% en {row.iloc[0].date() if hasattr(row.iloc[0], 'date') else row.iloc[0]}."
            )
        elif float(change) >= abs(threshold_pct):
            out.append(
                f"Subida brusca detectada: {float(change):.1f}% en {row.iloc[0].date() if hasattr(row.iloc[0], 'date') else row.iloc[0]}."
            )
    return out


def compute_concentration(
    breakdown_df: Optional[pd.DataFrame], category_col: Optional[str], metric_col: Optional[str]
) -> Optional[float]:
    if breakdown_df is None or breakdown_df.empty or not metric_col or metric_col not in breakdown_df.columns:
        return None
    total = float(breakdown_df[metric_col].sum())
    if total == 0:
        return None
    top1 = float(breakdown_df.iloc[0][metric_col])
    return (top1 / total) * 100
