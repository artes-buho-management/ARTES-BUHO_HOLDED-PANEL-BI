from __future__ import annotations

import io
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import Settings
from reporting.periods import PeriodInfo
from shared.analysis_service import AnalysisBundle


def build_report_pdf(
    output_path: str,
    report_type: str,
    period: PeriodInfo,
    analysis: AnalysisBundle,
    settings: Settings,
    source_sheet_name: str,
    source_detail: str,
) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles(settings)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.7 * cm,
        title=f"{period.report_title} - {settings.company_name}",
        author=settings.developer_name,
    )

    story: List = []
    story.extend(_cover_block(styles, period, settings))
    story.extend(_executive_summary(styles, report_type, period, analysis))
    story.extend(_kpi_block(styles, analysis))
    story.extend(_chart_block(styles, analysis, settings, report_type))
    story.extend(_detail_block(styles, report_type, analysis))
    story.extend(_insights_block(styles, analysis))
    story.extend(
        _methodology_block(
            styles=styles,
            source_sheet_name=source_sheet_name,
            source_detail=source_detail,
            timezone=settings.timezone,
        )
    )

    doc.build(
        story,
        onFirstPage=lambda c, d: _draw_footer(c, d, settings),
        onLaterPages=lambda c, d: _draw_footer(c, d, settings),
    )
    return str(output.resolve())


def _build_styles(settings: Settings):
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CorporateTitle",
            parent=styles["Title"],
            textColor=colors.HexColor(settings.brand_red),
            fontSize=20,
            leading=24,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CorporateH2",
            parent=styles["Heading2"],
            textColor=colors.HexColor(settings.brand_red),
            fontSize=13,
            leading=16,
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyClean",
            parent=styles["BodyText"],
            fontSize=10,
            leading=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallMuted",
            parent=styles["BodyText"],
            fontSize=8,
            textColor=colors.HexColor("#666666"),
            leading=11,
        )
    )
    return styles


def _cover_block(styles, period: PeriodInfo, settings: Settings) -> List:
    items: List = []
    logo = _build_logo(settings)

    right_text = (
        f"<b>{settings.company_name}</b><br/>"
        f"{period.report_title}<br/>"
        f"Periodo: {period.period_label}<br/>"
        f"Generado: {period.run_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}<br/>"
        f"Desarrollador del sistema: {settings.developer_name}"
    )
    header_table = Table(
        [[logo, Paragraph(right_text, styles["BodyClean"])]],
        colWidths=[4.4 * cm, 11.6 * cm],
        hAlign="LEFT",
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.HexColor(settings.brand_yellow)),
            ]
        )
    )

    items.append(Paragraph(period.report_title, styles["CorporateTitle"]))
    items.append(header_table)
    items.append(Spacer(1, 0.25 * cm))
    return items


def _executive_summary(styles, report_type: str, period: PeriodInfo, analysis: AnalysisBundle) -> List:
    items: List = [Paragraph("Resumen ejecutivo", styles["CorporateH2"])]

    base_text = (
        f"Informe {report_type} con cobertura {period.period_label}. "
        f"Se analizan {analysis.kpis.total_rows:,} filas en el periodo."
    )
    lines = [base_text]
    if analysis.kpis.principal_total is not None:
        lines.append(
            f"Metrica principal ({analysis.selected_metric}): {analysis.kpis.principal_total:,.2f}."
        )
    if analysis.kpis.delta_vs_previous is not None:
        direction = "sube" if analysis.kpis.delta_vs_previous >= 0 else "baja"
        lines.append(
            f"Comparado con periodo anterior, la metrica {direction} {abs(analysis.kpis.delta_vs_previous):.1f}%."
        )

    items.append(Paragraph(" ".join(lines), styles["BodyClean"]))
    return items


def _kpi_block(styles, analysis: AnalysisBundle) -> List:
    items: List = [Paragraph("KPIs principales", styles["CorporateH2"])]
    rows = [["Indicador", "Valor"]]
    rows.append(["Filas analizadas", f"{analysis.kpis.total_rows:,}"])
    rows.append(
        [
            f"Total ({analysis.selected_metric or 'metrica principal'})",
            "-"
            if analysis.kpis.principal_total is None
            else f"{analysis.kpis.principal_total:,.2f}",
        ]
    )
    rows.append(
        [
            "Media",
            "-"
            if analysis.kpis.principal_avg is None
            else f"{analysis.kpis.principal_avg:,.2f}",
        ]
    )
    rows.append(
        [
            "Mediana",
            "-"
            if analysis.kpis.principal_median is None
            else f"{analysis.kpis.principal_median:,.2f}",
        ]
    )
    rows.append(
        [
            "Delta vs periodo anterior",
            "-"
            if analysis.kpis.delta_vs_previous is None
            else f"{analysis.kpis.delta_vs_previous:+.1f}%",
        ]
    )
    table = _styled_table(
        rows=rows,
        col_widths=[8.2 * cm, 7.8 * cm],
        header_bg="#FFE8A3",
        font_size=9,
        align_last_col_right=True,
    )
    items.append(table)
    return items


def _chart_block(
    styles,
    analysis: AnalysisBundle,
    settings: Settings,
    report_type: str,
) -> List:
    items: List = [Paragraph("Visualizaciones relevantes", styles["CorporateH2"])]
    chart_rows = []

    ts_image = _build_time_series_image(analysis, settings)
    if ts_image:
        chart_rows.append(ts_image)

    cat_image = _build_category_image(analysis, settings)
    if cat_image:
        chart_rows.append(cat_image)

    if report_type == "annual":
        monthly_image = _build_monthly_summary_image(analysis, settings)
        if monthly_image:
            chart_rows.append(monthly_image)

    if not chart_rows:
        items.append(Paragraph("No hay datos suficientes para graficos robustos.", styles["BodyClean"]))
        return items

    for img in chart_rows:
        items.append(img)
        items.append(Spacer(1, 0.2 * cm))
    return items


def _detail_block(styles, report_type: str, analysis: AnalysisBundle) -> List:
    items: List = [Paragraph("Detalle de datos", styles["CorporateH2"])]
    df = analysis.filtered_df.copy()
    if df.empty:
        items.append(Paragraph("No hay filas para detalle en este periodo.", styles["BodyClean"]))
        return items

    max_rows = 12 if report_type == "weekly" else 18 if report_type == "monthly" else 24
    cols = list(df.columns[:6])
    preview = df[cols].head(max_rows).copy()
    preview = preview.fillna("")
    data = [cols] + preview.astype(str).values.tolist()
    col_width = 16.0 * cm / max(1, len(cols))
    table = _styled_table(
        rows=data,
        col_widths=[col_width] * len(cols),
        header_bg="#FDE4A8",
        font_size=8,
        alternate_rows=True,
    )
    items.append(table)
    return items


def _insights_block(styles, analysis: AnalysisBundle) -> List:
    items: List = [Paragraph("Insights automaticos", styles["CorporateH2"])]
    if not analysis.insights:
        items.append(Paragraph("No se detectan insights suficientes para este periodo.", styles["BodyClean"]))
        return items

    for insight in analysis.insights[:8]:
        items.append(Paragraph(f"- {insight}", styles["BodyClean"]))
    return items


def _methodology_block(styles, source_sheet_name: str, source_detail: str, timezone: str) -> List:
    text = (
        f"Metodologia breve: datos extraidos de Google Sheets. "
        f"Pestana analizada: {source_sheet_name}. "
        f"Origen tecnico: {source_detail}. "
        f"Zona horaria aplicada: {timezone}. "
        "Las metricas se generan con reglas deterministas y los insights son descriptivos."
    )
    return [
        Spacer(1, 0.15 * cm),
        Paragraph("Nota metodologica", styles["CorporateH2"]),
        Paragraph(text, styles["SmallMuted"]),
    ]


def _build_logo(settings: Settings):
    logo_path = Path(settings.logo_path)
    if logo_path.exists():
        return Image(str(logo_path), width=3.4 * cm, height=3.4 * cm)

    fallback = Table(
        [[Paragraph("<b>AB</b>", getSampleStyleSheet()["Title"])]],
        colWidths=[3.4 * cm],
        rowHeights=[3.4 * cm],
    )
    fallback.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(settings.brand_yellow)),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(settings.brand_red)),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(settings.brand_red)),
            ]
        )
    )
    return fallback


def _build_time_series_image(analysis: AnalysisBundle, settings: Settings):
    if analysis.ts_df is None or analysis.ts_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 2.6), dpi=140)
    ax.plot(
        analysis.ts_df.iloc[:, 0],
        analysis.ts_df["valor"],
        color=settings.brand_red,
        linewidth=2,
        marker="o",
        markersize=3,
    )
    ax.set_title("Evolucion temporal", fontsize=10)
    ax.grid(alpha=0.2)
    ax.tick_params(axis="x", labelrotation=25, labelsize=7)
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()

    return _figure_to_image(fig, width_cm=16.0, height_cm=5.0)


def _build_category_image(analysis: AnalysisBundle, settings: Settings):
    if not analysis.breakdowns:
        return None

    first_dim = list(analysis.breakdowns.keys())[0]
    data = analysis.breakdowns[first_dim].head(8)
    if data.empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 2.6), dpi=140)
    y_values = data.iloc[:, 1].astype(float).values
    labels = data[first_dim].astype(str).values
    ax.bar(labels, y_values, color=settings.brand_yellow, edgecolor=settings.brand_red)
    ax.set_title(f"Top por {first_dim}", fontsize=10)
    ax.tick_params(axis="x", rotation=25, labelsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()

    return _figure_to_image(fig, width_cm=16.0, height_cm=5.0)


def _build_monthly_summary_image(analysis: AnalysisBundle, settings: Settings):
    if not analysis.date_col or not analysis.selected_metric:
        return None
    if analysis.date_col not in analysis.filtered_df.columns:
        return None
    if analysis.selected_metric not in analysis.filtered_df.columns:
        return None

    temp = analysis.filtered_df[[analysis.date_col, analysis.selected_metric]].copy()
    temp[analysis.date_col] = pd.to_datetime(temp[analysis.date_col], errors="coerce")
    temp[analysis.selected_metric] = pd.to_numeric(
        temp[analysis.selected_metric], errors="coerce"
    )
    temp = temp.dropna()
    if temp.empty:
        return None

    monthly = (
        temp.set_index(analysis.date_col)[analysis.selected_metric]
        .resample("M")
        .sum()
        .reset_index()
    )
    if monthly.empty:
        return None

    labels = monthly[analysis.date_col].dt.strftime("%Y-%m").tolist()
    values = monthly[analysis.selected_metric].astype(float).tolist()

    fig, ax = plt.subplots(figsize=(8, 2.6), dpi=140)
    ax.plot(labels, values, color=settings.brand_red, linewidth=2, marker="o", markersize=3)
    ax.set_title("Resumen mensual (informe anual)", fontsize=10)
    ax.grid(axis="y", alpha=0.2)
    ax.tick_params(axis="x", rotation=30, labelsize=7)
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()

    return _figure_to_image(fig, width_cm=16.0, height_cm=5.0)


def _figure_to_image(fig, width_cm: float, height_cm: float):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width_cm * cm, height=height_cm * cm)


def _styled_table(
    rows,
    col_widths,
    header_bg: str,
    font_size: int,
    align_last_col_right: bool = False,
    alternate_rows: bool = False,
):
    table = Table(rows, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E0E0E0")),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if align_last_col_right:
        style.append(("ALIGN", (-1, 1), (-1, -1), "RIGHT"))
    if alternate_rows:
        style.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FCFCFC")]))
    table.setStyle(TableStyle(style))
    return table


def _draw_footer(canvas, doc, settings: Settings) -> None:
    canvas.saveState()
    footer_y = 1.1 * cm
    canvas.setStrokeColor(colors.HexColor(settings.brand_yellow))
    canvas.setLineWidth(0.8)
    canvas.line(doc.leftMargin, footer_y + 0.35 * cm, A4[0] - doc.rightMargin, footer_y + 0.35 * cm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor(settings.brand_red))
    canvas.drawString(
        doc.leftMargin,
        footer_y,
        f"{settings.company_name} | Sistema: {settings.developer_name}",
    )
    canvas.drawRightString(
        A4[0] - doc.rightMargin,
        footer_y,
        f"Pagina {canvas.getPageNumber()}",
    )
    canvas.restoreState()
