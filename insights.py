from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from analytics import KPIBundle


def build_executive_insights(
    kpis: KPIBundle,
    time_series_df: Optional[pd.DataFrame],
    breakdowns: Dict[str, pd.DataFrame],
    anomalies: List[str],
    metric_label: Optional[str],
) -> List[str]:
    messages: List[str] = []

    if kpis.principal_metric and kpis.principal_total is not None:
        messages.append(
            f"El total de {metric_label or kpis.principal_metric} en el filtro actual es {kpis.principal_total:,.2f}."
        )

    if kpis.delta_vs_previous is not None:
        direction = "crece" if kpis.delta_vs_previous >= 0 else "cae"
        messages.append(
            f"La metrica principal {direction} {abs(kpis.delta_vs_previous):.1f}% frente al periodo anterior."
        )

    if time_series_df is not None and not time_series_df.empty:
        recent = time_series_df.tail(3)["valor"]
        if len(recent) >= 3:
            trend_up = bool(recent.iloc[-1] >= recent.iloc[0])
            messages.append(
                "La tendencia reciente es alcista." if trend_up else "La tendencia reciente es bajista."
            )

    for category, data in breakdowns.items():
        if data.empty:
            continue
        top_row = data.iloc[0]
        col_metric = data.columns[1]
        messages.append(
            f"En {category}, lidera '{top_row[category]}' con {float(top_row[col_metric]):,.2f}."
        )
        break

    if anomalies:
        messages.extend(anomalies[:3])

    if not messages:
        messages.append("No hay suficiente señal para generar insights robustos en el filtro actual.")

    return messages
