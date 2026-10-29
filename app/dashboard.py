"""
FINHYPE – Interactive Treasury Liquidity & Mutual Fund Flow Forecasting Dashboard.
Phase 5: Production Dashboard & Cash Buffer Recommendation Engine.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path so 'app' package is always resolvable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from app.services.cash_buffer import (
    calculate_cash_buffer_recommendation,
    get_default_base_buffer_pct,
    get_preferred_model,
)
from app.services.forward_forecasting import (
    generate_3month_forward_forecasts,
    get_forward_recommendation,
)

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FINHYPE | Treasury Liquidity & Fund Flow Forecasting",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_PATH = ROOT / "data" / "processed" / "featured_fund_flows.csv"
BACKTEST_PATH = ROOT / "data" / "processed" / "backtest_results.csv"
SUMMARY_PATH = ROOT / "data" / "processed" / "backtest_metrics_summary.csv"
FORWARD_PATH = ROOT / "data" / "processed" / "forward_forecasts_3m.csv"


@st.cache_data
def load_all_data():
    """Load and cache precomputed historical data, backtest metrics, and forward forecasts."""
    df_hist = pd.read_csv(DATA_PATH) if DATA_PATH.exists() else None
    df_bkt = pd.read_csv(BACKTEST_PATH) if BACKTEST_PATH.exists() else None
    df_sum = pd.read_csv(SUMMARY_PATH) if SUMMARY_PATH.exists() else None
    
    if FORWARD_PATH.exists():
        df_fwd = pd.read_csv(FORWARD_PATH)
    else:
        df_fwd = generate_3month_forward_forecasts()
        
    return df_hist, df_bkt, df_sum, df_fwd


df_hist, df_bkt, df_sum, df_fwd = load_all_data()

# Graceful missing data guard
if df_hist is None or df_bkt is None or df_sum is None or df_fwd is None:
    st.error(
        "### ⚠️ Processed Datasets Not Found\n\n"
        "The FINHYPE dashboard requires precomputed feature matrices, backtest evaluation records, "
        "and forward forecast artifacts.\n\n"
        "**To generate all required datasets and run verification tests, execute:**\n"
        "```bash\n"
        "python run_pipeline.py\n"
        "# or on Windows:\n"
        ".\\run.ps1\n"
        "```\n"
        "*(Artifacts are cached in `data/processed/` and reused across sessions.)*"
    )
    st.stop()

# ── Sidebar Filters & Global Settings ─────────────────────────────────────────
st.sidebar.title("📈 FINHYPE Navigation")
st.sidebar.caption("Zeckathon 2026 · Problem Statement 3")

selected_category = st.sidebar.selectbox(
    "Select Fund Category",
    options=["Liquid Fund", "Overnight Fund"],
    index=0,
    help="Liquid Funds invest in debt instruments up to 91 days; Overnight Funds invest in 1-day maturity paper.",
)

st.sidebar.divider()
st.sidebar.markdown("### ⚙️ Treasury Buffer Settings")

selected_horizon = st.sidebar.slider(
    "Planning Horizon (Months)",
    min_value=1,
    max_value=3,
    value=3,
    step=1,
    help="Select forecast horizon (1M = Oct 2026, 2M = Oct-Nov 2026, 3M = Oct-Dec 2026).",
)

selected_risk = st.sidebar.selectbox(
    "Risk Tolerance Profile",
    options=[
        "Moderate (80% 2-Sided / 90% Downside Coverage)",
        "Conservative (95% 2-Sided / 97.5% Downside Coverage)",
        "Aggressive (Expected Central Flow)",
    ],
    index=0,
    help="Higher confidence widens prediction intervals to ensure higher coverage against acute drawdowns.",
)

selected_trajectory = st.sidebar.radio(
    "Multi-Month Policy Mode",
    options=[
        "Single-Model Trajectory (Production Baseline)",
        "Step-Wise Stitched Trajectory (Alternative)",
    ],
    index=0,
    help=(
        "Single-Model Baseline evaluates a single dynamically coherent model family across all steps "
        "(e.g., Seasonal-Naive for multi-month Overnight). "
        "Step-Wise Stitched alternative selects the empirical champion model at each horizon step."
    ),
)
is_stitched = (selected_trajectory == "Step-Wise Stitched Trajectory (Alternative)")

default_base_pct = get_default_base_buffer_pct(selected_category)
user_base_pct = st.sidebar.slider(
    "Base Operational Floor (% of AUM)",
    min_value=0.0,
    max_value=15.0,
    value=float(default_base_pct),
    step=0.5,
    help="Minimum liquidity cushion maintained for intra-month operational churn.",
)

st.sidebar.divider()
st.sidebar.info(
    "**Forecast Origin:** September 2026\n\n"
    "**Forward Target Months:** Oct, Nov, Dec 2026\n\n"
    "**Historical Horizon:** Apr 2019 – Sep 2026 (90M)\n\n"
    "**Currency Units:** INR Crore (₹ Cr)"
)


# ── Title & Header ────────────────────────────────────────────────────────────
st.title("FINHYPE: Liquidity Management & Mutual Fund Flow Forecasting")
st.markdown(
    "**Monthly net flow forecasting and dynamic cash-buffer sizing for Indian Liquid and Overnight Mutual Funds.** "
    "Designed to pre-position treasury liquidity ahead of corporate advance-tax drains and quarterly balance-sheet closures."
)

st.divider()

# ── Tabs Navigation ───────────────────────────────────────────────────────────
tabs = st.tabs([
    "🏛️ Executive Summary",
    "📊 Historical Dynamics & AUM",
    "🎯 3-Month Forward Forecasts",
    "🛡️ Cash Buffer Recommendation",
    "⚖️ Model Benchmark & Backtest",
    "ℹ️ Data Freshness & Methodology"
])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1: EXECUTIVE SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.header("Executive Summary: Liquidity Landscape")
    
    # Filter historical category
    cat_df = df_hist[df_hist["category"] == selected_category].sort_values("month").reset_index(drop=True)
    latest_row = cat_df.iloc[-1]
    prev_row = cat_df.iloc[-2]
    
    current_aum = float(latest_row["aum_cr"])
    current_net_flow = float(latest_row["net_inflow_cr"])
    current_mobilised = float(latest_row["funds_mobilised_cr"])
    current_redemption = float(latest_row["redemption_cr"])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Current Fund AUM (Sep 2026)",
            value=f"₹{current_aum:,.0f} Cr",
            delta=f"{((current_aum - prev_row['aum_cr']) / prev_row['aum_cr'] * 100):+.1f}% MoM",
        )
    with col2:
        flow_color = "normal" if current_net_flow >= 0 else "inverse"
        st.metric(
            label="Latest Monthly Net Flow (Sep 2026)",
            value=f"₹{current_net_flow:+,.0f} Cr",
            delta=f"₹{(current_net_flow - prev_row['net_inflow_cr']):+,.0f} Cr MoM",
            delta_color=flow_color,
        )
    with col3:
        st.metric(
            label="Gross Monthly Volume Mobilised",
            value=f"₹{current_mobilised:,.0f} Cr",
            help="Total gross subscriptions entered in September 2026.",
        )
    with col4:
        st.metric(
            label="Gross Redemptions Executed",
            value=f"₹{current_redemption:,.0f} Cr",
            help="Total repurchases paid out in September 2026.",
        )
        
    st.markdown("---")
    
    # Key insights callouts
    st.subheader("Key Findings & Liquidity Posture")
    
    ec1, ec2 = st.columns([1.5, 1])
    with ec1:
        st.markdown(
            """
            * **The Quarter-End Tax Drain**: Institutional flows in India exhibit powerful cyclical contractions in 
              **March, June, September, and December** driven by corporate advance-tax deadlines and banking window dressing.
            * **Immediate Post-Quarter Rebound**: Liquid fund flows surge back in **October, January, April, and July**. 
              For October 2026, the model projects a positive liquidity rebound of **+₹75,821 Cr**.
            * **High Portfolio Velocity**: Liquid funds turn over ~**1.04x** of total AUM every month, while Overnight funds 
              turn over **5.44x of total AUM monthly** (~₹420,000 Cr in gross monthly transactions).
            * **Category-Specific Top Models**: Empirical backtests show **SARIMAX** outperforms for Liquid Funds across all horizons 
              (**+14.55% Skill Score** at Horizon 1), while Seasonal-Naive persistence achieves superior accuracy 
              for Overnight Funds beyond 1 month.
            """
        )
    with ec2:
        st.markdown("#### 🔍 Active Treasury Recommendation")
        rec_exec = get_forward_recommendation(
            category=selected_category,
            horizon_months=selected_horizon,
            risk_tolerance="moderate" if "Moderate" in selected_risk else ("conservative" if "Conservative" in selected_risk else "aggressive"),
            base_buffer_pct=user_base_pct,
            forward_df=df_fwd,
            step_wise_preferred=is_stitched,
        )
        st.success(
            f"**Recommended Cash Buffer ({selected_horizon}M Horizon):**\n\n"
            f"### ₹{rec_exec.recommended_buffer_cr:,.0f} Cr  \n"
            f"*(**{rec_exec.recommended_buffer_pct_aum:.1f}%** of Fund AUM)*\n\n"
            f"**Preferred Model:** `{rec_exec.preferred_model.upper()}` | **Confidence:** {rec_exec.confidence_level_pct}%"
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2: HISTORICAL DYNAMICS & AUM
# ═════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.header(f"Historical Net Flows & Asset Trajectory: {selected_category}")
    st.caption("Observation window: April 2019 to September 2026 (90 continuous monthly records).")
    
    fig_hist = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=[
            f"<b>{selected_category}: Monthly Net Flows (INR Crore)</b>",
            f"<b>{selected_category}: Assets Under Management (INR Crore)</b>",
        ]
    )
    
    # Net flow bars (Green for inflow, Red for outflow)
    colors = ["#22c55e" if v >= 0 else "#ef4444" for v in cat_df["net_inflow_cr"]]
    fig_hist.add_trace(
        go.Bar(
            x=cat_df["month"],
            y=cat_df["net_inflow_cr"],
            marker_color=colors,
            name="Net Flow",
            hovertemplate="<b>%{x}</b><br>Net Flow: ₹%{y:,.0f} Cr<extra></extra>",
        ),
        row=1, col=1
    )
    fig_hist.add_hline(y=0, line_dash="solid", line_color="#334155", line_width=1, row=1, col=1)
    
    # AUM line
    fig_hist.add_trace(
        go.Scatter(
            x=cat_df["month"],
            y=cat_df["aum_cr"],
            mode="lines",
            line=dict(color="#3b82f6", width=2.5),
            name="Month-End AUM",
            hovertemplate="<b>%{x}</b><br>AUM: ₹%{y:,.0f} Cr<extra></extra>",
        ),
        row=2, col=1
    )
    
    fig_hist.update_layout(height=650, template="plotly_white", showlegend=False, margin=dict(l=50, r=30, t=60, b=40))
    fig_hist.update_xaxes(showgrid=True, gridcolor="#e2e8f0", tickangle=45)
    fig_hist.update_yaxes(showgrid=True, gridcolor="#e2e8f0")
    st.plotly_chart(fig_hist, use_container_width=True)
    
    # Seasonal breakdown by month
    st.subheader("Calendar Month Seasonality Profile")
    m_season = cat_df.groupby("calendar_month")["net_inflow_cr"].agg(["mean", "median", "std"]).reset_index()
    month_names = {
        1: "Jan (Rebound)", 2: "Feb", 3: "Mar (FY Tax)", 4: "Apr (Rebound)",
        5: "May", 6: "Jun (Q1 Tax)", 7: "Jul (Rebound)", 8: "Aug",
        9: "Sep (Q2 Tax)", 10: "Oct (Rebound)", 11: "Nov", 12: "Dec (Q3 Tax)"
    }
    m_season["month_label"] = m_season["calendar_month"].map(month_names)
    
    fig_season = go.Figure()
    bar_colors = ["#ef4444" if m in [3, 6, 9, 12] else "#2563eb" for m in m_season["calendar_month"]]
    fig_season.add_trace(
        go.Bar(
            x=m_season["month_label"],
            y=m_season["mean"],
            marker_color=bar_colors,
            text=[f"₹{v:+,.0f} Cr" for v in m_season["mean"]],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Mean Flow: ₹%{y:,.0f} Cr<extra></extra>",
        )
    )
    fig_season.add_hline(y=0, line_dash="solid", line_color="black")
    fig_season.update_layout(
        title="<b>Average Monthly Net Inflow/Outflow by Calendar Month (Advance Tax vs Rebound)</b>",
        height=450,
        template="plotly_white",
        xaxis_title="Calendar Month",
        yaxis_title="Average Net Flow (INR Crore)",
        margin=dict(l=50, r=30, t=60, b=50),
    )
    st.plotly_chart(fig_season, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3: 3-MONTH FORWARD FORECASTS
# ═════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.header(f"Out-of-Sample Forward Projections: {selected_category}")
    st.caption("Forecast Horizon: October 2026, November 2026, December 2026 (Origin: September 2026).")
    
    cat_fwd = df_fwd[df_fwd["category"] == selected_category].sort_values(["model_name", "horizon"]).reset_index(drop=True)
    
    def format_model_label(x: str) -> str:
        if x == "policy_trajectory":
            pol_desc = "Step-Wise Stitched Alternative" if is_stitched else "Single-Model Baseline"
            return f"🛡️ Active Cash-Buffer Policy Trajectory ({pol_desc})"
        if selected_category == "Liquid Fund":
            return f"{x.upper()} (Top-Performing: 1M-3M)" if x == "sarimax" else x.upper()
        else:
            if x == "sarimax":
                return f"{x.upper()} (Top-Performing: 1M)"
            elif x == "seasonal_naive":
                return f"{x.upper()} (Top-Performing: 2M-3M)"
            return x.upper()

    fwd_model = st.selectbox(
        "Display Forecast Model / Trajectory",
        options=["policy_trajectory", "sarimax", "seasonal_naive", "ets", "ridge"],
        index=0,
        format_func=format_model_label,
        help="Select 'Active Cash-Buffer Policy Trajectory' to view the exact model path deployed in Tab 4, or choose an individual candidate model to explore its unconstrained 3-month forecast.",
    )
    
    if fwd_model == "policy_trajectory":
        rows = []
        for h in [1, 2, 3]:
            if is_stitched:
                h_model = get_preferred_model(selected_category, h)
            else:
                h_model = get_preferred_model(selected_category, selected_horizon)
            match = cat_fwd[(cat_fwd["model_name"] == h_model) & (cat_fwd["horizon"] == h)]
            if not match.empty:
                rows.append(match.iloc[0])
        model_fwd = pd.DataFrame(rows).reset_index(drop=True)
        active_models_label = " + ".join([r.upper() for r in model_fwd["model_name"].tolist()])
        st.success(
            f"**🛡️ Active Treasury Buffer Policy View ({'Step-Wise Stitched Alternative' if is_stitched else 'Single-Model Baseline'}):** "
            f"Displaying the exact model sequence deployed for liquidity sizing in Tab 4: `{active_models_label}`. "
            f"Point forecasts and prediction intervals are strictly matched to each horizon's selected model."
        )
    else:
        model_fwd = cat_fwd[cat_fwd["model_name"] == fwd_model].sort_values("horizon").reset_index(drop=True)
        policy_model_desc = (
            "SARIMAX (Month 1) + Seasonal-Naive (Months 2 & 3)" if (selected_category == "Overnight Fund" and is_stitched)
            else ("Seasonal-Naive (all 3 months)" if (selected_category == "Overnight Fund" and selected_horizon >= 2)
            else "SARIMAX (all 3 months)")
        )
        st.info(
            f"ℹ️ **Standalone Model Exploration Mode ({fwd_model.upper()}):** "
            f"Viewing pure 3-month trajectory for {fwd_model.upper()}. "
            f"Note: The deployed treasury cash buffer policy uses **{policy_model_desc}** (switch dropdown to *Active Cash-Buffer Policy Trajectory* above or navigate to Tab 4 for treasury buffer sizing)."
        )
    
    # Forward trajectory chart with fan bands
    fig_fwd = go.Figure()
    
    # Historical context: last 6 months
    last_6m = cat_df.tail(6)
    fig_fwd.add_trace(
        go.Scatter(
            x=last_6m["month"],
            y=last_6m["net_inflow_cr"],
            mode="lines+markers",
            line=dict(color="#64748b", width=2),
            marker=dict(size=6),
            name="Historical Actuals",
            hovertemplate="<b>%{x}</b><br>Actual: ₹%{y:,.0f} Cr<extra></extra>",
        )
    )
    
    # Connecting line from last historical point to first forecast
    x_proj = [last_6m["month"].iloc[-1]] + model_fwd["target_month"].tolist()
    y_proj = [last_6m["net_inflow_cr"].iloc[-1]] + model_fwd["predicted_cr"].tolist()
    
    # 95% interval band
    fig_fwd.add_trace(
        go.Scatter(
            x=model_fwd["target_month"].tolist() + model_fwd["target_month"].tolist()[::-1],
            y=model_fwd["upper_95"].tolist() + model_fwd["lower_95"].tolist()[::-1],
            fill="toself",
            fillcolor="rgba(59, 130, 246, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            hoverinfo="skip",
            name="95% Prediction Interval",
        )
    )
    
    # 80% interval band
    fig_fwd.add_trace(
        go.Scatter(
            x=model_fwd["target_month"].tolist() + model_fwd["target_month"].tolist()[::-1],
            y=model_fwd["upper_80"].tolist() + model_fwd["lower_80"].tolist()[::-1],
            fill="toself",
            fillcolor="rgba(59, 130, 246, 0.30)",
            line=dict(color="rgba(255,255,255,0)"),
            hoverinfo="skip",
            name="80% Prediction Interval",
        )
    )
    
    # Point forecast line
    point_line_name = (
        f"Active Policy ({active_models_label})"
        if fwd_model == "policy_trajectory"
        else f"{fwd_model.upper()} Point Forecast"
    )
    fig_fwd.add_trace(
        go.Scatter(
            x=x_proj,
            y=y_proj,
            mode="lines+markers",
            line=dict(color="#1d4ed8", width=3, dash="dot"),
            marker=dict(size=8, symbol="diamond"),
            name=point_line_name,
            hovertemplate="<b>%{x}</b><br>Forecast: ₹%{y:,.0f} Cr<extra></extra>",
        )
    )
    
    chart_model_desc = (
        f"Active Treasury Policy Trajectory"
        if fwd_model == "policy_trajectory"
        else fwd_model.upper()
    )
    fig_fwd.add_hline(y=0, line_dash="solid", line_color="black", line_width=1)
    fig_fwd.update_layout(
        title=f"<b>{selected_category}: Forward Net Flow Trajectory ({chart_model_desc})</b>",
        height=500,
        template="plotly_white",
        yaxis_title="Net Fund Flow (INR Crore)",
        xaxis_title="Timeline",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=30, t=60, b=40),
    )
    st.plotly_chart(fig_fwd, use_container_width=True)
    
    # Detailed forward breakdown table with compact sub-tabs for responsive reading
    st.subheader("Forward Projections Breakdown Table (INR Crore)")
    st.caption("Calibrated out-of-sample prediction intervals for upcoming 3-month forward horizon (Origin: September 2026).")
    
    df_fwd_table = model_fwd[[
        "target_month", "horizon", "model_name", "predicted_cr",
        "lower_80", "upper_80", "lower_95", "upper_95"
    ]].copy()
    df_fwd_table["model_name"] = df_fwd_table["model_name"].str.upper()
    
    tab_all, tab_80, tab_95 = st.tabs([
        "📋 Complete Summary (All Bands)",
        "🛡️ Moderate Risk View (80% Interval)",
        "⚠️ Conservative Stress View (95% Interval)",
    ])
    
    with tab_all:
        df_all = df_fwd_table.copy()
        df_all.columns = [
            "Month", "Horizon", "Model", "Forecast (₹ Cr)",
            "80% Lower (q10)", "80% Upper (q90)",
            "95% Lower (q025)", "95% Upper (q975)",
        ]
        st.dataframe(
            df_all.style.format({
                "Forecast (₹ Cr)": "{:+,.2f}",
                "80% Lower (q10)": "{:+,.2f}",
                "80% Upper (q90)": "{:+,.2f}",
                "95% Lower (q025)": "{:+,.2f}",
                "95% Upper (q975)": "{:+,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
    
    with tab_80:
        df_80 = df_fwd_table[[
            "target_month", "horizon", "model_name", "predicted_cr", "lower_80", "upper_80"
        ]].copy()
        df_80.columns = ["Month", "Horizon", "Model", "Forecast (₹ Cr)", "80% Lower (q10)", "80% Upper (q90)"]
        st.dataframe(
            df_80.style.format({
                "Forecast (₹ Cr)": "{:+,.2f}",
                "80% Lower (q10)": "{:+,.2f}",
                "80% Upper (q90)": "{:+,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("ℹ️ *q10 denotes the 10th percentile empirical error bound, providing 90% one-sided downside protection against liquidity outflows.*")
    
    with tab_95:
        df_95 = df_fwd_table[[
            "target_month", "horizon", "model_name", "predicted_cr", "lower_95", "upper_95"
        ]].copy()
        df_95.columns = ["Month", "Horizon", "Model", "Forecast (₹ Cr)", "95% Lower (q025)", "95% Upper (q975)"]
        st.dataframe(
            df_95.style.format({
                "Forecast (₹ Cr)": "{:+,.2f}",
                "95% Lower (q025)": "{:+,.2f}",
                "95% Upper (q975)": "{:+,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("⚠️ *q025 denotes the 2.5th percentile empirical error bound, providing 97.5% one-sided downside protection under severe liquidity stress.*")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4: CASH BUFFER RECOMMENDATION ENGINE
# ═════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.header(f"Dynamic Treasury Cash Buffer Recommendation: {selected_category}")
    st.caption("Actionable liquidity sizing parameterized by risk tolerance and peak cumulative deficit.")
    
    risk_code = "conservative" if "Conservative" in selected_risk else ("moderate" if "Moderate" in selected_risk else "aggressive")
    rec = get_forward_recommendation(
        category=selected_category,
        horizon_months=selected_horizon,
        risk_tolerance=risk_code,
        base_buffer_pct=user_base_pct,
        forward_df=df_fwd,
        step_wise_preferred=is_stitched,
    )
    
    policy_label = "Step-Wise Stitched Trajectory (Alternative)" if is_stitched else "Single-Model Trajectory (Production Baseline)"
    st.info(
        f"**Active Buffer Policy:** `{policy_label}` | **Model Architecture:** `{rec.preferred_model.upper()}` | **Horizon:** {rec.horizon_months} Month(s)\n\n"
        + (
            "• Evaluates the empirical top model at each individual horizon step (e.g. SARIMAX at 1M, Seasonal-Naive at 2M & 3M) with strictly matched error quantiles."
            if is_stitched
            else "• Evaluates a single coherent model family across all horizon steps (Seasonal-Naive for multi-month Overnight, SARIMAX for Liquid)."
        )
    )
    
    # Top Recommendation Cards
    rc1, rc2, rc3, rc4 = st.columns(4)
    with rc1:
        st.metric(
            label="Recommended Buffer (Total)",
            value=f"₹{rec.recommended_buffer_cr:,.0f} Cr",
            help="Total recommended cash buffer required to absorb peak downside deficit and operational friction.",
        )
    with rc2:
        st.metric(
            label="Buffer as % of AUM",
            value=f"{rec.recommended_buffer_pct_aum:.2f}%",
            help="Proportion of total fund assets to be held in cash, overnight sovereign repos, or T-Bills.",
        )
    with rc3:
        st.metric(
            label="Peak Downside Deficit",
            value=f"₹{rec.cumulative_downside_deficit_cr:,.0f} Cr",
            help="Maximum cumulative net outflow projected over the selected planning horizon.",
        )
    with rc4:
        st.metric(
            label="Base Operational Floor",
            value=f"₹{rec.base_operational_buffer_cr:,.0f} Cr",
            help="Minimum operational liquidity cushion based on user-configured percentage of AUM.",
        )
        
    st.markdown("---")

    if selected_category == "Overnight Fund" and selected_horizon >= 2:
        with st.expander("🔍 Compare Overnight Buffer Policies: Single-Model Baseline vs Step-Wise Stitched Trajectory", expanded=False):
            comp_rec_single = get_forward_recommendation(
                category="Overnight Fund", horizon_months=selected_horizon, risk_tolerance=risk_code,
                base_buffer_pct=user_base_pct, forward_df=df_fwd, step_wise_preferred=False
            )
            comp_rec_stitch = get_forward_recommendation(
                category="Overnight Fund", horizon_months=selected_horizon, risk_tolerance=risk_code,
                base_buffer_pct=user_base_pct, forward_df=df_fwd, step_wise_preferred=True
            )
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.markdown("##### 🏛️ Single-Model Baseline (Seasonal-Naive)")
                st.markdown(f"- **Recommended Buffer:** ₹{comp_rec_single.recommended_buffer_cr:,.0f} Cr (**{comp_rec_single.recommended_buffer_pct_aum:.2f}% of AUM**)")
                st.markdown(f"- **Peak Cumulative Deficit:** ₹{comp_rec_single.cumulative_downside_deficit_cr:,.0f} Cr")
                st.caption("Evaluates a single dynamical persistence family across all months.")
            with col_b2:
                st.markdown("##### 🔀 Step-Wise Stitched Alternative")
                st.markdown(f"- **Recommended Buffer:** ₹{comp_rec_stitch.recommended_buffer_cr:,.0f} Cr (**{comp_rec_stitch.recommended_buffer_pct_aum:.2f}% of AUM**)")
                st.markdown(f"- **Peak Cumulative Deficit:** ₹{comp_rec_stitch.cumulative_downside_deficit_cr:,.0f} Cr")
                st.caption("Stitches SARIMAX at H=1 and Seasonal-Naive at H=2, 3 with strictly matched error quantiles.")
    
    # Visual Watermark Chart of Buffer Components
    st.subheader(f"Step-by-Step Cumulative Liquidity Trajectory ({rec.horizon_months}-Month Horizon)")
    
    m_steps = [f"Month {item['month_step']}" for item in rec.monthly_breakdown]
    f_flows = [item["forecast_net_flow_cr"] for item in rec.monthly_breakdown]
    d_flows = [item["effective_downside_cr"] for item in rec.monthly_breakdown]
    c_deficits = [item["cumulative_deficit_cr"] for item in rec.monthly_breakdown]
    
    fig_buffer = go.Figure()
    fig_buffer.add_trace(
        go.Bar(
            x=m_steps,
            y=f_flows,
            name="Point Forecast Flow",
            marker_color="#3b82f6",
            hovertemplate="Forecast Flow: ₹%{y:,.0f} Cr<extra></extra>",
        )
    )
    fig_buffer.add_trace(
        go.Bar(
            x=m_steps,
            y=d_flows,
            name="Downside Outflow (10th/2.5th %ile Bound)",
            marker_color="#ef4444",
            hovertemplate="Downside Outflow: ₹%{y:,.0f} Cr<extra></extra>",
        )
    )
    fig_buffer.add_trace(
        go.Scatter(
            x=m_steps,
            y=c_deficits,
            mode="lines+markers",
            name="Cumulative Liquidity Deficit",
            line=dict(color="#f59e0b", width=3),
            marker=dict(size=10),
            hovertemplate="Cumulative Deficit: ₹%{y:,.0f} Cr<extra></extra>",
        )
    )
    fig_buffer.add_hline(
        y=rec.recommended_buffer_cr,
        line_dash="dash",
        line_color="#dc2626",
        annotation_text=f"Recommended Buffer: ₹{rec.recommended_buffer_cr:,.0f} Cr",
        annotation_position="top left",
    )
    fig_buffer.update_layout(
        title="<b>Monthly Expected vs Downside Net Flow and Required Buffer Coverage</b>",
        barmode="group",
        height=450,
        template="plotly_white",
        yaxis_title="INR Crore",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=30, t=60, b=40),
    )
    st.plotly_chart(fig_buffer, use_container_width=True)
    
    # Methodology clarification banner
    st.info(
        "ℹ️ **Methodology Note on Multi-Month Planning Horizons**: "
        "Summing monthly downside bounds represents a **conservative comonotonic stress-test scenario** "
        "(assuming consecutive adverse shocks), rather than a statistically calibrated multi-month joint prediction interval. "
        "Nominal interval coverage reflects historical empirical frequency and does not guarantee protection against "
        "unprecedented tail-risk shocks or intraday corporate cash runs."
    )
    
    if selected_category == "Overnight Fund" and selected_horizon >= 2:
        st.warning(
            "⚠️ **Outlier Sensitivity Note (Overnight Fund Multi-Month Horizon)**: "
            "The multi-month Overnight Fund cash buffer recommendation (₹74,130.35 Cr under Moderate / 80% and ₹118,049.89 Cr under Conservative / 95% at 3M) "
            "is heavily influenced by the extreme historical outlier of November 2025 (-₹37,624.53 Cr), which Seasonal-Naive replicates for November 2026. "
            "Compounding this severe historical observation with empirical downside error percentiles yields an acute comonotonic stress requirement. "
            "These figures are preserved without artificial suppression to maintain analytical transparency and historical integrity."
        )
    
    # Monthly breakdown audit table
    st.markdown("#### Monthly Deficit Progression Table")
    st.caption("Detailed step-by-step progression showing the specific model, point forecast, calibrated downside bound, and cumulative liquidity deficit at each horizon step.")
    
    df_rec_breakdown = pd.DataFrame(rec.monthly_breakdown)
    target_months = ["2026-10", "2026-11", "2026-12"][:len(df_rec_breakdown)]
    if "+" in rec.preferred_model:
        models = [m.upper() for m in rec.preferred_model.split("+")[:len(df_rec_breakdown)]]
    else:
        models = [rec.preferred_model.upper()] * len(df_rec_breakdown)
        
    df_rec_breakdown.insert(1, "Target Month", target_months)
    df_rec_breakdown.insert(2, "Model", models)
    
    df_rec_breakdown.columns = [
        "Step", "Month", "Model", "Forecast (₹ Cr)", "Downside Bound (₹ Cr)", "Upper Bound (₹ Cr)",
        "Effective Downside (₹ Cr)", "Cumulative Forecast (₹ Cr)",
        "Cumulative Downside (₹ Cr)", "Cumulative Deficit (₹ Cr)"
    ]
    st.dataframe(
        df_rec_breakdown.style.format({
            "Forecast (₹ Cr)": "{:+,.2f}",
            "Downside Bound (₹ Cr)": "{:+,.2f}",
            "Upper Bound (₹ Cr)": "{:+,.2f}",
            "Effective Downside (₹ Cr)": "{:+,.2f}",
            "Cumulative Forecast (₹ Cr)": "{:+,.2f}",
            "Cumulative Downside (₹ Cr)": "{:+,.2f}",
            "Cumulative Deficit (₹ Cr)": "{:+,.2f}",
        }),
        use_container_width=True,
        hide_index=True,
    )
    
    # Warnings and Governance notes
    st.markdown("#### ⚠️ Governance, Assumptions & Disclaimers")
    for w in rec.warnings:
        st.warning(w, icon="⚠️")
        
    with st.expander("View Calculation Assumptions"):
        st.json(rec.assumptions)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5: MODEL BENCHMARK & BACKTEST
# ═════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.header(f"Rolling-Origin Backtest Benchmark: {selected_category}")
    st.caption("Evaluated across 24 monthly forecast origins (July 2024 through June 2026).")
    
    cat_summary = df_sum[df_sum["category"] == selected_category].copy()
    
    # Model comparative bar chart
    fig_cmp = px.bar(
        cat_summary[cat_summary["horizon"] != "all"],
        x="horizon",
        y="mae_cr",
        color="model_name",
        barmode="group",
        labels={"horizon": "Forecast Horizon (Months)", "mae_cr": "MAE (INR Crore)", "model_name": "Model"},
        title=f"<b>Mean Absolute Error by Horizon: {selected_category} (Lower is Better)</b>",
        color_discrete_map={
            "sarimax": "#2563eb",
            "seasonal_naive": "#10b981",
            "ets": "#f59e0b",
            "ridge": "#8b5cf6"
        }
    )
    fig_cmp.update_layout(height=450, template="plotly_white", margin=dict(l=50, r=30, t=60, b=40))
    st.plotly_chart(fig_cmp, use_container_width=True)
    
    # Summary Metrics Table
    st.subheader("Audited Backtest Metrics Table")
    
    display_summary = cat_summary[[
        "model_name", "horizon", "mae_cr", "rmse_cr", "wape_pct",
        "mape_pct", "mase", "coverage_80_pct", "coverage_95_pct",
        "rel_mae", "skill_score", "fallbacks_count"
    ]].copy()
    
    display_summary.columns = [
        "Model", "Horizon", "MAE (₹ Cr)", "RMSE (₹ Cr)", "WAPE (%)",
        "MAPE (%)", "MASE", "80% Coverage (%)", "95% Coverage (%)",
        "Rel MAE", "Skill Score", "Failures"
    ]
    
    st.dataframe(
        display_summary.style.format({
            "MAE (₹ Cr)": "₹{:,.2f}",
            "RMSE (₹ Cr)": "₹{:,.2f}",
            "WAPE (%)": "{:.2f}%",
            "MAPE (%)": "{:.2f}%",
            "MASE": "{:.4f}",
            "80% Coverage (%)": "{:.1f}%",
            "95% Coverage (%)": "{:.1f}%",
            "Rel MAE": "{:.4f}",
            "Skill Score": "{:+.2%}",
            "Failures": "{:d}",
        }),
        use_container_width=True,
    )
    
    st.markdown(
        """
        **Metric Interpretation Guide:**
        * **Skill Score**: Improvement relative to Seasonal-Naive benchmark ($1 - \text{MAE}_{\text{model}} / \text{MAE}_{\text{baseline}}$). 
          Positive values indicate the model successfully outperforms simple annual repetition.
        * **MASE**: Mean Absolute Scaled Error relative to in-sample seasonal differences. Values $< 1.0$ indicate model superiority.
        * **Coverage**: Percentage of the 24 evaluation origins where actual ground truth fell inside the prediction interval.
        """
    )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 6: DATA FRESHNESS & METHODOLOGY
# ═════════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.header("Data Freshness, Governance & Methodological Architecture")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🗄️ Official Data Sources")
        st.markdown(
            """
            * **AMFI Monthly Reports**: Official monthly Excel statements from the Association of Mutual Funds in India (AMFI).
              * Frequency: Monthly
              * Coverage: April 2019 to September 2026 (90 continuous months)
              * Records: 180 verified records (0 missing values, 0 duplicate keys)
            * **Reserve Bank of India (RBI)**: Official Monetary Policy Committee (MPC) Repo Rate decisions.
              * Frequency: Monthly effective rate
              * Units: Percent per annum (% p.a.)
            * **National Stock Exchange (NSE)**: Nifty 50 Benchmark Index.
              * Frequency: Monthly closing level and percentage return
            """
        )
    with c2:
        st.markdown("### 📐 Macroeconomic Forward Assumptions")
        st.markdown(
            r"""
            * **Zero Macro Leakage**: Under no circumstances are realized future macroeconomic numbers used during multi-step forecasting.
            * **Constant Forward Policy Rate**: For forward horizons $h \in \{1, 2, 3\}$, the RBI repo rate is assumed constant 
              at the latest observed rate ($\Delta \text{Repo}_{T+h} = 0$).
            * **Neutral Equity Sentiment**: Nifty 50 returns are assumed neutral ($\text{Return}_{T+h} = 0$).
            * **Deterministic Calendar**: Calendar flags (`is_advance_tax_month`, `is_quarter_end`, `is_fy_end`) 
              are mathematically fixed and known in advance.
            """
        )
        
    st.divider()
    st.markdown("### ⚠️ Methodological Limitations & Model Governance")
    st.markdown(
        r"""
        1. **Sample Granularity (24 Origins)**: Each missed observation in the 24 backtest origins accounts for **$4.17\%$** 
           of empirical coverage. Consequently, 95% coverage cannot be distinguished from 85% or 99% with high statistical confidence; 
           the 80% coverage provides the more reliable calibration signal.
        2. **Multi-Step Horizon Dependency**: Forecast errors for $h=2$ and $h=3$ across consecutive months overlap in calendar time, 
           forming an autocorrelated $\text{MA}(h-1)$ structure.
        3. **Aggregate Monthly Limitations**: AMFI reports provide monthly aggregate flows. Acute intra-month cash runs 
           (e.g., between the 15th and 20th of advance-tax months) cannot be observed directly from monthly reports. 
           Fund managers must maintain the base operational floor for daily settlement volatility.
        """
    )
    st.caption("FINHYPE · Zeckathon 2026 · Problem Statement 3 · Phase 5 Verified")
