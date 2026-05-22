from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics import compute_concentration
from config import Settings, get_settings
from data_loader import LoadResult, load_google_sheets_data
from data_processing import ProcessedData, clean_and_prepare
from shared.analysis_service import (
    choose_sheet_name,
    execute_analysis,
    get_filter_options,
)


st.set_page_config(
    page_title="Panel Analitico Automatico",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=900, show_spinner=True)
def cached_load_data(settings: Settings) -> LoadResult:
    return load_google_sheets_data(settings)


@st.cache_data(ttl=900, show_spinner=False)
def cached_process(df: pd.DataFrame) -> ProcessedData:
    return clean_and_prepare(df)


def main() -> None:
    settings = get_settings()
    _render_header(settings)

    try:
        load_result = cached_load_data(settings)
    except Exception as exc:
        st.error(f"No se pudo cargar Google Sheets: {exc}")
        st.stop()

    if not load_result.sheets:
        st.warning("No hay datos en la hoja fuente.")
        st.stop()

    sheet_names = list(load_result.sheets.keys())
    default_sheet = choose_sheet_name(load_result, settings.preferred_worksheet)
    default_idx = sheet_names.index(default_sheet) if default_sheet in sheet_names else 0

    st.sidebar.header("Filtros")
    selected_sheet = st.sidebar.selectbox("Pestana origen", sheet_names, index=default_idx)
    raw_df = load_result.sheets[selected_sheet]

    processed = cached_process(raw_df)
    df = processed.dataframe

    if df.empty:
        st.warning("La pestana seleccionada no contiene datos analizables.")
        _render_quality(processed)
        st.stop()

    selected_metric, date_range, category_filters = _build_sidebar_filters(processed)

    analysis = execute_analysis(
        processed=processed,
        date_range=date_range,
        category_filters=category_filters,
        forced_metric=selected_metric,
        anomaly_threshold_pct=45.0,
    )

    _render_kpis(analysis.kpis)
    _render_insights(analysis.insights)
    _render_charts(
        analysis.ts_df,
        analysis.breakdowns,
        analysis.filtered_df,
        analysis.selected_metric,
    )
    _render_table(analysis.filtered_df)
    _render_notes(
        settings,
        load_result,
        selected_sheet,
        analysis.selected_metric,
        analysis.breakdowns,
    )
    _render_quality(processed)


def _build_sidebar_filters(
    processed: ProcessedData,
) -> tuple[Optional[str], Optional[tuple[pd.Timestamp, pd.Timestamp]], Dict[str, List[str]]]:
    options = get_filter_options(processed)
    date_col = options["date_col"]
    selected_metric = options["metric_col"]
    date_range = options["date_range"]

    if date_range and date_col:
        min_dt, max_dt = date_range
        if pd.notna(min_dt) and pd.notna(max_dt):
            picked = st.sidebar.date_input(
                "Rango de fechas",
                value=(min_dt.date(), max_dt.date()),
                min_value=min_dt.date(),
                max_value=max_dt.date(),
            )
            if isinstance(picked, tuple) and len(picked) == 2:
                date_range = (pd.Timestamp(picked[0]), pd.Timestamp(picked[1]))

    category_filters: Dict[str, List[str]] = {}
    category_values = options["category_values"]
    for col, values in category_values.items():
        selected = st.sidebar.multiselect(
            col,
            options=values,
            default=values[: min(8, len(values))],
        )
        if selected:
            category_filters[col] = selected

    return selected_metric, date_range, category_filters


def _render_header(settings: Settings) -> None:
    st.title(settings.panel_name)
    st.caption(settings.panel_description)
    st.caption(f"Actualizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def _render_kpis(kpis) -> None:
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Filas analizadas", f"{kpis.total_rows:,}")
    col2.metric(
        "Total metrica principal",
        "-" if kpis.principal_total is None else f"{kpis.principal_total:,.2f}",
        None
        if kpis.delta_vs_previous is None
        else f"{kpis.delta_vs_previous:+.1f}% vs periodo anterior",
    )
    col3.metric(
        "Media metrica principal",
        "-" if kpis.principal_avg is None else f"{kpis.principal_avg:,.2f}",
    )
    col4.metric(
        "Mediana metrica principal",
        "-" if kpis.principal_median is None else f"{kpis.principal_median:,.2f}",
    )


def _render_insights(insights: List[str]) -> None:
    st.subheader("Insights automaticos")
    for msg in insights:
        st.markdown(f"- {msg}")


def _render_charts(
    ts_df: Optional[pd.DataFrame],
    breakdowns: Dict[str, pd.DataFrame],
    filtered_df: pd.DataFrame,
    metric_col: Optional[str],
) -> None:
    st.subheader("Visualizaciones")

    if ts_df is not None and not ts_df.empty:
        fig_ts = px.line(
            ts_df,
            x=ts_df.columns[0],
            y="valor",
            markers=True,
            title="Evolucion temporal",
        )
        st.plotly_chart(fig_ts, use_container_width=True)

    show_count = 0
    for category, data in breakdowns.items():
        if data.empty:
            continue
        fig = px.bar(
            data.head(10),
            x=category,
            y=data.columns[1],
            title=f"Top categorias por {category}",
        )
        st.plotly_chart(fig, use_container_width=True)
        show_count += 1
        if show_count >= 2:
            break

    if metric_col and metric_col in filtered_df.columns:
        numeric = pd.to_numeric(filtered_df[metric_col], errors="coerce").dropna()
        if len(numeric) >= 10:
            fig_hist = px.histogram(
                numeric,
                nbins=30,
                title=f"Distribucion de {metric_col}",
            )
            st.plotly_chart(fig_hist, use_container_width=True)


def _render_table(filtered_df: pd.DataFrame) -> None:
    st.subheader("Tabla detallada")
    st.dataframe(filtered_df, use_container_width=True, height=380)


def _render_notes(
    settings: Settings,
    load_result: LoadResult,
    selected_sheet: str,
    selected_metric: Optional[str],
    breakdowns: Dict[str, pd.DataFrame],
) -> None:
    st.subheader("Notas operativas")
    st.markdown(f"- Fuente: Google Sheets ({load_result.source_type})")
    st.markdown(f"- Detalle de carga: {load_result.details}")
    st.markdown(f"- Pestana activa: {selected_sheet}")
    st.markdown(f"- Metrica principal: {selected_metric or 'No detectada'}")

    if breakdowns and selected_metric:
        first_dim = list(breakdowns.keys())[0]
        concentration = compute_concentration(
            breakdowns[first_dim], first_dim, breakdowns[first_dim].columns[1]
        )
        if concentration is not None:
            st.markdown(
                f"- Concentracion top 1 en {first_dim}: {concentration:.1f}% (vigilancia si supera 60%)."
            )

    if settings.streamlit_public_url:
        st.markdown(f"- URL panel: {settings.streamlit_public_url}")


def _render_quality(processed: ProcessedData) -> None:
    with st.expander("Calidad y normalizacion del dato"):
        st.json(processed.quality_report)
        mapping_df = pd.DataFrame(
            [
                {
                    "original": original,
                    "normalizado": normalized,
                    "tipo": processed.inferred_types.get(normalized, ""),
                    "rol_semantico": processed.semantic_roles.get(normalized, ""),
                }
                for original, normalized in processed.column_map.items()
            ]
        )
        st.dataframe(mapping_df, use_container_width=True, height=260)


if __name__ == "__main__":
    main()

