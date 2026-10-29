"""
Exploratory Data Analysis (EDA) module for FINHYPE.

Computes descriptive statistics, seasonal decomposition, quarter-end tax impacts,
outlier detection, and cross-category relationships for Indian Liquid and Overnight Funds.
Generates reproducible interactive Plotly visualizations.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def compute_category_summary_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute comprehensive descriptive statistics for each fund category.
    """
    metrics = []
    for cat in ["Liquid Fund", "Overnight Fund"]:
        sub = df[df["category"] == cat]
        flows = sub["net_inflow_cr"]
        aum = sub["aum_cr"]
        mob = sub["funds_mobilised_cr"]
        red = sub["redemption_cr"]
        turnover = (mob + red) / (2 * aum)
        
        metrics.append({
            "category": cat,
            "months_count": len(sub),
            "net_flow_mean_cr": round(float(flows.mean()), 2),
            "net_flow_std_cr": round(float(flows.std()), 2),
            "net_flow_median_cr": round(float(flows.median()), 2),
            "net_flow_iqr_cr": round(float(flows.quantile(0.75) - flows.quantile(0.25)), 2),
            "net_flow_min_cr": round(float(flows.min()), 2),
            "net_flow_max_cr": round(float(flows.max()), 2),
            "skewness": round(float(flows.skew()), 3),
            "kurtosis": round(float(flows.kurt()), 3),
            "avg_aum_cr": round(float(aum.mean()), 2),
            "avg_monthly_mobilisation_cr": round(float(mob.mean()), 2),
            "avg_monthly_redemption_cr": round(float(red.mean()), 2),
            "avg_turnover_ratio": round(float(turnover.mean()), 2),
        })
        
    return pd.DataFrame(metrics)


def compute_quarter_end_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare fund flow dynamics between Quarter-End months (Mar, Jun, Sep, Dec)
    and Non-Quarter-End months.
    """
    df_calc = df.copy()
    df_calc["is_quarter_end"] = df_calc["month_num"].isin([3, 6, 9, 12])
    
    rows = []
    for cat in ["Liquid Fund", "Overnight Fund"]:
        sub = df_calc[df_calc["category"] == cat]
        qe = sub[sub["is_quarter_end"]]["net_inflow_cr"]
        non_qe = sub[~sub["is_quarter_end"]]["net_inflow_cr"]
        
        rows.append({
            "category": cat,
            "qe_mean_net_flow_cr": round(float(qe.mean()), 2),
            "qe_std_net_flow_cr": round(float(qe.std()), 2),
            "qe_median_net_flow_cr": round(float(qe.median()), 2),
            "non_qe_mean_net_flow_cr": round(float(non_qe.mean()), 2),
            "non_qe_std_net_flow_cr": round(float(non_qe.std()), 2),
            "non_qe_median_net_flow_cr": round(float(non_qe.median()), 2),
            "diff_qe_minus_non_qe_cr": round(float(qe.mean() - non_qe.mean()), 2),
        })
    return pd.DataFrame(rows)


def compute_monthly_seasonality(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate calendar month seasonality (months 1-12) for both categories.
    """
    month_names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    
    records = []
    for m in range(1, 13):
        rec: Dict[str, Any] = {
            "month_num": m,
            "month_name": month_names[m],
            "is_advance_tax_month": m in [3, 6, 9, 12],
            "is_post_quarter_month": m in [1, 4, 7, 10],
        }
        for cat in ["Liquid Fund", "Overnight Fund"]:
            sub = df[(df["category"] == cat) & (df["month_num"] == m)]
            prefix = "liquid" if "Liquid" in cat else "overnight"
            rec[f"{prefix}_mean_net_flow_cr"] = round(float(sub["net_inflow_cr"].mean()), 2)
            rec[f"{prefix}_median_net_flow_cr"] = round(float(sub["net_inflow_cr"].median()), 2)
            rec[f"{prefix}_std_net_flow_cr"] = round(float(sub["net_inflow_cr"].std()), 2)
        records.append(rec)
        
    return pd.DataFrame(records)


def detect_outliers(df: pd.DataFrame, z_threshold: float = 2.0) -> pd.DataFrame:
    """
    Identify outlier months using standard Z-score on net inflows per category.
    """
    outliers = []
    for cat in ["Liquid Fund", "Overnight Fund"]:
        sub = df[df["category"] == cat].copy()
        mean = sub["net_inflow_cr"].mean()
        std = sub["net_inflow_cr"].std()
        sub["z_score"] = (sub["net_inflow_cr"] - mean) / std
        
        cat_outliers = sub[sub["z_score"].abs() >= z_threshold].copy()
        for _, row in cat_outliers.iterrows():
            outliers.append({
                "month": row["month"],
                "month_label": row["month_label"],
                "category": cat,
                "net_inflow_cr": round(float(row["net_inflow_cr"]), 2),
                "z_score": round(float(row["z_score"]), 2),
                "type": "Extreme Inflow" if row["z_score"] > 0 else "Extreme Outflow",
            })
    return pd.DataFrame(outliers).sort_values(by=["category", "month"]).reset_index(drop=True)


# --- Visualizations ---

def plot_net_flows_time_series(df: pd.DataFrame, output_path: str) -> None:
    """
    Generate interactive Plotly time series of monthly net flows for both categories.
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=[
            "<b>Liquid Fund: Monthly Net Flows (INR Crore)</b>",
            "<b>Overnight Fund: Monthly Net Flows (INR Crore)</b>"
        ]
    )
    
    df_liq = df[df["category"] == "Liquid Fund"].sort_values("month")
    df_ovn = df[df["category"] == "Overnight Fund"].sort_values("month")
    
    # Liquid bar colors (green for inflow, red for outflow)
    liq_colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df_liq["net_inflow_cr"]]
    ovn_colors = ["#3b82f6" if v >= 0 else "#f97316" for v in df_ovn["net_inflow_cr"]]
    
    fig.add_trace(
        go.Bar(
            x=df_liq["month"],
            y=df_liq["net_inflow_cr"],
            name="Liquid Net Flow",
            marker_color=liq_colors,
            hovertemplate="<b>%{x}</b><br>Net Flow: ₹%{y:,.0f} Cr<extra></extra>",
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(
            x=df_ovn["month"],
            y=df_ovn["net_inflow_cr"],
            name="Overnight Net Flow",
            marker_color=ovn_colors,
            hovertemplate="<b>%{x}</b><br>Net Flow: ₹%{y:,.0f} Cr<extra></extra>",
        ),
        row=2, col=1
    )
    
    fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1, row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1, row=2, col=1)
    
    fig.update_layout(
        title="<b>FINHYPE: Monthly Net Inflow/Outflow Trajectory (Apr 2019 - Sep 2026)</b>",
        height=750,
        showlegend=False,
        template="plotly_white",
        font=dict(family="Arial, sans-serif", size=12),
        margin=dict(l=60, r=40, t=80, b=60),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0", tickangle=45)
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0", title_text="Net Flow (INR Cr)")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn")


def plot_gross_flows_comparison(df: pd.DataFrame, output_path: str) -> None:
    """
    Generate charts comparing gross mobilisations, redemptions, and net flows.
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=[
            "<b>Liquid Fund: Gross Churn (Mobilisations vs. Redemptions)</b>",
            "<b>Overnight Fund: Gross Churn (Mobilisations vs. Redemptions)</b>"
        ]
    )
    
    df_liq = df[df["category"] == "Liquid Fund"].sort_values("month")
    df_ovn = df[df["category"] == "Overnight Fund"].sort_values("month")
    
    fig.add_trace(
        go.Scatter(
            x=df_liq["month"], y=df_liq["funds_mobilised_cr"],
            name="Liquid Mobilisations", line=dict(color="#10b981", width=2),
            hovertemplate="Mobilised: ₹%{y:,.0f} Cr<extra></extra>"
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df_liq["month"], y=df_liq["redemption_cr"],
            name="Liquid Redemptions", line=dict(color="#f43f5e", width=2, dash="dot"),
            hovertemplate="Redemption: ₹%{y:,.0f} Cr<extra></extra>"
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df_ovn["month"], y=df_ovn["funds_mobilised_cr"],
            name="Overnight Mobilisations", line=dict(color="#0284c7", width=2),
            hovertemplate="Mobilised: ₹%{y:,.0f} Cr<extra></extra>"
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df_ovn["month"], y=df_ovn["redemption_cr"],
            name="Overnight Redemptions", line=dict(color="#f97316", width=2, dash="dot"),
            hovertemplate="Redemption: ₹%{y:,.0f} Cr<extra></extra>"
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title="<b>FINHYPE: Monthly Gross Liquidity Churn Analysis</b>",
        height=750,
        template="plotly_white",
        font=dict(family="Arial, sans-serif", size=12),
        margin=dict(l=60, r=40, t=80, b=60),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0", tickangle=45)
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0", title_text="Gross Volume (INR Cr)")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn")


def plot_seasonality_calendar_month(df: pd.DataFrame, output_path: str) -> None:
    """
    Generate seasonality chart showing average net flows by calendar month (1-12).
    """
    season_df = compute_monthly_seasonality(df)
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Bar(
            x=season_df["month_name"],
            y=season_df["liquid_mean_net_flow_cr"],
            name="Liquid Fund Mean Net Flow",
            marker_color="#2563eb",
            hovertemplate="<b>%{x}</b><br>Liquid Mean: ₹%{y:,.0f} Cr<extra></extra>"
        )
    )
    
    fig.add_trace(
        go.Bar(
            x=season_df["month_name"],
            y=season_df["overnight_mean_net_flow_cr"],
            name="Overnight Fund Mean Net Flow",
            marker_color="#f59e0b",
            hovertemplate="<b>%{x}</b><br>Overnight Mean: ₹%{y:,.0f} Cr<extra></extra>"
        )
    )
    
    fig.add_hline(y=0, line_dash="solid", line_color="#334155", line_width=1.5)
    
    fig.update_layout(
        title="<b>FINHYPE: Monthly Calendar Seasonality (Advance Tax & Rebound Cycles)</b>",
        barmode="group",
        height=600,
        template="plotly_white",
        font=dict(family="Arial, sans-serif", size=12),
        xaxis_title="Calendar Month",
        yaxis_title="Average Net Inflow/Outflow (INR Crore)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=80, b=60),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0")
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn")


def plot_quarter_end_effect(df: pd.DataFrame, output_path: str) -> None:
    """
    Generate box plots illustrating the stark Quarter-End Outflow vs. Non-Quarter-End Inflow distribution.
    """
    df_plot = df.copy()
    df_plot["Period Type"] = df_plot["month_num"].apply(
        lambda m: "Quarter-End Month (Mar/Jun/Sep/Dec)" if m in [3, 6, 9, 12] else "Non-Quarter-End Month"
    )
    
    fig = go.Figure()
    
    colors = {"Liquid Fund": "#3b82f6", "Overnight Fund": "#10b981"}
    
    for cat in ["Liquid Fund", "Overnight Fund"]:
        sub = df_plot[df_plot["category"] == cat]
        fig.add_trace(
            go.Box(
                x=sub["Period Type"],
                y=sub["net_inflow_cr"],
                name=cat,
                marker_color=colors[cat],
                boxmean=True,
                hovertemplate="<b>%{x}</b><br>%{y:,.0f} Cr<extra></extra>"
            )
        )
        
    fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1)
    
    fig.update_layout(
        title="<b>FINHYPE: Quarter-End Liquidity Contraction vs. Regular Months</b>",
        boxmode="group",
        height=600,
        template="plotly_white",
        font=dict(family="Arial, sans-serif", size=12),
        xaxis_title="Calendar Horizon",
        yaxis_title="Net Inflow/Outflow (INR Crore)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=80, b=60),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn")


def plot_outlier_analysis(df: pd.DataFrame, output_path: str) -> None:
    """
    Generate visual display of statistical outliers and extreme events.
    """
    outliers_df = detect_outliers(df, z_threshold=2.0)
    
    fig = go.Figure()
    
    for cat, col in [("Liquid Fund", "#2563eb"), ("Overnight Fund", "#10b981")]:
        sub = df[df["category"] == cat].sort_values("month")
        fig.add_trace(
            go.Scatter(
                x=sub["month"],
                y=sub["net_inflow_cr"],
                mode="lines+markers",
                name=cat,
                line=dict(color=col, width=1.5),
                marker=dict(size=4)
            )
        )
        
    # Annotate top extreme outliers
    for _, row in outliers_df.iterrows():
        fig.add_annotation(
            x=row["month"],
            y=row["net_inflow_cr"],
            text=f"<b>{row['month']}:</b> {row['net_inflow_cr']:+,.0f} Cr",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor="#ef4444",
            ax=0,
            ay=-30 if row["net_inflow_cr"] > 0 else 30,
            font=dict(size=10, color="#1e293b")
        )
        
    fig.add_hline(y=0, line_dash="solid", line_color="black", line_width=1)
    
    fig.update_layout(
        title="<b>FINHYPE: Outlier & Shock Detection (|Z-Score| >= 2.0)</b>",
        height=700,
        template="plotly_white",
        font=dict(family="Arial, sans-serif", size=12),
        xaxis_title="Month",
        yaxis_title="Net Inflow/Outflow (INR Crore)",
        margin=dict(l=60, r=40, t=80, b=60),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0", tickangle=45)
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn")


def plot_category_cross_correlation(df: pd.DataFrame, output_path: str) -> None:
    """
    Generate cross-category scatter plot and rolling correlation between Liquid and Overnight funds.
    """
    piv = df.pivot(index="month", columns="category", values="net_inflow_cr").reset_index()
    piv = piv.dropna()
    piv = piv.sort_values("month")
    
    # Calculate rolling 12-month correlation
    piv["rolling_corr_12"] = piv["Liquid Fund"].rolling(12).corr(piv["Overnight Fund"])
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[
            "<b>Net Flows: Liquid vs. Overnight Scatter</b>",
            "<b>12-Month Rolling Correlation Over Time</b>"
        ],
        horizontal_spacing=0.12
    )
    
    # Scatter
    fig.add_trace(
        go.Scatter(
            x=piv["Liquid Fund"],
            y=piv["Overnight Fund"],
            mode="markers",
            marker=dict(size=8, color="#6366f1", opacity=0.8),
            text=piv["month"],
            hovertemplate="<b>%{text}</b><br>Liquid: ₹%{x:,.0f} Cr<br>Overnight: ₹%{y:,.0f} Cr<extra></extra>",
            name="Monthly Co-movement"
        ),
        row=1, col=1
    )
    
    # Add OLS regression trendline
    slope, intercept = np.polyfit(piv["Liquid Fund"], piv["Overnight Fund"], 1)
    x_range = np.linspace(piv["Liquid Fund"].min(), piv["Liquid Fund"].max(), 100)
    fig.add_trace(
        go.Scatter(
            x=x_range,
            y=slope * x_range + intercept,
            mode="lines",
            line=dict(color="#ef4444", dash="dash", width=2),
            name=f"Trendline (r = {piv['Liquid Fund'].corr(piv['Overnight Fund']):.2f})"
        ),
        row=1, col=1
    )
    
    # Rolling correlation line
    fig.add_trace(
        go.Scatter(
            x=piv["month"],
            y=piv["rolling_corr_12"],
            mode="lines+markers",
            line=dict(color="#0ea5e9", width=2),
            marker=dict(size=4),
            name="12-Month Rolling Corr",
            hovertemplate="<b>%{x}</b><br>Rolling Corr: %{y:.3f}<extra></extra>"
        ),
        row=1, col=2
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=2)
    
    fig.update_layout(
        title="<b>FINHYPE: Cross-Category Interdependence (Liquid vs. Overnight)</b>",
        height=550,
        template="plotly_white",
        font=dict(family="Arial, sans-serif", size=12),
        margin=dict(l=60, r=40, t=80, b=60),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0", title_text="Liquid Fund Net Flow (Cr)", row=1, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0", title_text="Overnight Fund Net Flow (Cr)", row=1, col=1)
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0", title_text="Month", tickangle=45, row=1, col=2)
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0", title_text="Pearson Correlation", row=1, col=2)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.write_html(output_path, include_plotlyjs="cdn")

