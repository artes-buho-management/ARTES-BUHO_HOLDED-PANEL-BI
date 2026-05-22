from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from analytics import (
    KPIBundle,
    apply_filters,
    build_category_breakdown,
    build_time_series,
    choose_primary_sheet,
    compute_kpis,
    detect_simple_anomalies,
)
from config import Settings
from data_loader import LoadResult, load_google_sheets_data
from data_processing import ProcessedData, clean_and_prepare, find_relevant_columns
from insights import build_executive_insights


@dataclass
class AnalysisBundle:
    processed: ProcessedData
    filtered_df: pd.DataFrame
    date_col: Optional[str]
    metric_cols: List[str]
    category_cols: List[str]
    selected_metric: Optional[str]
    kpis: KPIBundle
    ts_df: Optional[pd.DataFrame]
    breakdowns: Dict[str, pd.DataFrame]
    anomalies: List[str]
    insights: List[str]


def load_source_sheets(settings: Settings) -> LoadResult:
    return load_google_sheets_data(settings)


def choose_sheet_name(
    load_result: LoadResult, preferred_sheet: str = ""
) -> str:
    if preferred_sheet and preferred_sheet in load_result.sheets:
        return preferred_sheet
    return choose_primary_sheet(load_result.sheets)


def prepare_sheet(raw_df: pd.DataFrame) -> ProcessedData:
    return clean_and_prepare(raw_df)


def default_date_range(
    df: pd.DataFrame, date_col: Optional[str]
) -> Optional[Tuple[pd.Timestamp, pd.Timestamp]]:
    if not date_col or date_col not in df.columns:
        return None

    min_dt = pd.to_datetime(df[date_col], errors="coerce").min()
    max_dt = pd.to_datetime(df[date_col], errors="coerce").max()
    if pd.isna(min_dt) or pd.isna(max_dt):
        return None
    return pd.Timestamp(min_dt), pd.Timestamp(max_dt)


def get_analysis_columns(processed: ProcessedData) -> Dict[str, List[str]]:
    return find_relevant_columns(processed.dataframe, processed.semantic_roles)


def get_filter_options(
    processed: ProcessedData,
    max_filter_columns: int = 4,
    max_values_per_column: int = 50,
) -> Dict[str, object]:
    df = processed.dataframe
    cols = get_analysis_columns(processed)

    date_col = cols["date_cols"][0] if cols["date_cols"] else None
    metric_col = cols["metric_cols"][0] if cols["metric_cols"] else None
    category_cols = cols["category_cols"][:max_filter_columns]

    category_values: Dict[str, List[str]] = {}
    for col in category_cols:
        top_values = (
            df[col]
            .dropna()
            .astype(str)
            .value_counts()
            .head(max_values_per_column)
            .index.tolist()
        )
        if top_values:
            category_values[col] = top_values

    return {
        "date_col": date_col,
        "metric_col": metric_col,
        "date_range": default_date_range(df, date_col),
        "category_values": category_values,
    }


def execute_analysis(
    processed: ProcessedData,
    date_range: Optional[Tuple[pd.Timestamp, pd.Timestamp]] = None,
    category_filters: Optional[Dict[str, List[str]]] = None,
    forced_metric: Optional[str] = None,
    anomaly_threshold_pct: float = 45.0,
) -> AnalysisBundle:
    base_df = processed.dataframe
    relevant = find_relevant_columns(base_df, processed.semantic_roles)
    date_cols = relevant["date_cols"]
    metric_cols = relevant["metric_cols"]
    category_cols = relevant["category_cols"]

    selected_date_col = date_cols[0] if date_cols else None
    selected_metric = forced_metric if forced_metric in metric_cols else None
    if selected_metric is None:
        selected_metric = metric_cols[0] if metric_cols else None

    filtered_df = apply_filters(
        base_df,
        selected_date_col,
        date_range,
        category_filters or {},
    )
    kpis = compute_kpis(filtered_df, metric_cols, selected_date_col)
    ts_df = build_time_series(filtered_df, selected_date_col, selected_metric)
    breakdowns = build_category_breakdown(filtered_df, category_cols, selected_metric)
    anomalies = detect_simple_anomalies(ts_df, threshold_pct=anomaly_threshold_pct)
    insights = build_executive_insights(
        kpis, ts_df, breakdowns, anomalies, selected_metric
    )

    return AnalysisBundle(
        processed=processed,
        filtered_df=filtered_df,
        date_col=selected_date_col,
        metric_cols=metric_cols,
        category_cols=category_cols,
        selected_metric=selected_metric,
        kpis=kpis,
        ts_df=ts_df,
        breakdowns=breakdowns,
        anomalies=anomalies,
        insights=insights,
    )
