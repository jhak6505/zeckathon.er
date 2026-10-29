"""
Feature Engineering Module for FINHYPE.

Constructs reproducible, leakage-free features for forecasting Indian Liquid
and Overnight mutual fund net flows across a 3-month forecast horizon.

Features include:
1. Calendar and Advance Tax indicators (Quarter-End, FY-End, Rebound months)
2. Autoregressive lags (lags 1, 2, 3, 6, 12)
3. Rolling statistics (mean, std, min, max over 3, 6, 12 months)
4. Gross flow churn and AUM scaling features
5. Cross-category peer indicators
6. Macroeconomic factors (RBI Policy Repo Rate and Nifty 50 Equity Benchmark)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.data.external_factors import build_external_factors_dataset

logger = logging.getLogger(__name__)

DEFAULT_INPUT_CSV = os.path.join("data", "processed", "fund_flows_monthly.csv")
DEFAULT_OUTPUT_CSV = os.path.join("data", "processed", "featured_fund_flows.csv")


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate deterministic calendar, cyclical, and corporate tax indicators.
    
    All calendar features are deterministic and known prior to the target period.
    """
    df = df.copy()
    
    # Parse month string YYYY-MM
    dates = pd.to_datetime(df["month"] + "-01")
    
    df["calendar_year"] = dates.dt.year
    df["calendar_month"] = dates.dt.month
    df["quarter"] = dates.dt.quarter
    df["days_in_month"] = dates.dt.days_in_month
    
    # Advance Corporate Tax Months in India:
    # 15 June (Q1 - 15%), 15 September (Q2 - 45%), 15 December (Q3 - 75%), 15 March (Q4 - 100%)
    df["is_advance_tax_month"] = df["calendar_month"].isin([3, 6, 9, 12]).astype(int)
    
    # Quarter-end months (coincide with advance tax + bank window dressing)
    df["is_quarter_end"] = df["calendar_month"].isin([3, 6, 9, 12]).astype(int)
    
    # Indian Financial Year-End (March) - by far the largest systemic liquidity drawdown
    df["is_fy_end"] = (df["calendar_month"] == 3).astype(int)
    
    # Post-quarter rebound months (January, April, July, October) where liquidity floods back
    df["is_post_quarter_month"] = df["calendar_month"].isin([1, 4, 7, 10]).astype(int)
    
    # Cyclical trigonometric encodings for month of year (preserves continuity between Dec and Jan)
    df["sin_month"] = np.round(np.sin(2 * np.pi * df["calendar_month"] / 12.0), 4)
    df["cos_month"] = np.round(np.cos(2 * np.pi * df["calendar_month"] / 12.0), 4)
    
    return df


def add_autoregressive_lags(
    df: pd.DataFrame,
    lags: List[int] = [1, 2, 3, 6, 12]
) -> pd.DataFrame:
    """
    Calculate autoregressive lags for net_inflow_cr.
    
    Crucially, groups by category and sorts chronologically before shifting.
    Lags strictly refer to prior periods (no forward-looking leakage).
    """
    df = df.copy()
    df = df.sort_values(by=["category", "month"]).reset_index(drop=True)
    
    for lag in lags:
        col_name = f"net_inflow_lag_{lag}"
        df[col_name] = df.groupby("category")["net_inflow_cr"].shift(lag)
        
    return df


def add_rolling_features(
    df: pd.DataFrame,
    windows: List[int] = [3, 6, 12]
) -> pd.DataFrame:
    """
    Compute rolling mean, standard deviation, min, and max of net flows.
    
    LEAKAGE PREVENTION:
    All rolling statistics are computed on the strictly shifted series (.shift(1)),
    meaning the rolling window for month t only includes observations up to month t-1.
    """
    df = df.copy()
    df = df.sort_values(by=["category", "month"]).reset_index(drop=True)
    
    # Shifted series to ensure no current-month data is included in rolling stats
    lag1_series = df.groupby("category")["net_inflow_cr"].shift(1)
    
    for w in windows:
        # Rolling group calculation
        df[f"net_inflow_roll_mean_{w}"] = (
            lag1_series.groupby(df["category"]).transform(lambda s: s.rolling(w).mean())
        )
        df[f"net_inflow_roll_std_{w}"] = (
            lag1_series.groupby(df["category"]).transform(lambda s: s.rolling(w).std())
        )
        if w == 3:
            df[f"net_inflow_roll_min_{w}"] = (
                lag1_series.groupby(df["category"]).transform(lambda s: s.rolling(w).min())
            )
            df[f"net_inflow_roll_max_{w}"] = (
                lag1_series.groupby(df["category"]).transform(lambda s: s.rolling(w).max())
            )
            
    return df


def add_gross_flow_and_aum_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute lagged gross flow metrics (mobilisations, redemptions, churn) and AUM indicators.
    
    All features are lagged by at least 1 month.
    """
    df = df.copy()
    df = df.sort_values(by=["category", "month"]).reset_index(drop=True)
    
    # Lag 1 of mobilisations, redemptions, and AUM
    df["funds_mobilised_lag_1"] = df.groupby("category")["funds_mobilised_cr"].shift(1)
    df["redemption_lag_1"] = df.groupby("category")["redemption_cr"].shift(1)
    df["aum_lag_1"] = df.groupby("category")["aum_cr"].shift(1)
    df["avg_aum_lag_1"] = df.groupby("category")["avg_aum_cr"].shift(1)
    
    # Lag 2 of AUM for month-over-month AUM growth calculation
    aum_lag_2 = df.groupby("category")["aum_cr"].shift(2)
    df["aum_growth_mom_lag_1"] = ((df["aum_lag_1"] - aum_lag_2) / aum_lag_2 * 100).round(2)
    
    # Lagged monthly churn ratio: (Mobilised + Redemption) / (2 * AUM)
    df["churn_ratio_lag_1"] = (
        (df["funds_mobilised_lag_1"] + df["redemption_lag_1"]) / (2.0 * df["aum_lag_1"])
    ).round(3)
    
    # Lagged flow to AUM intensity (% of fund size)
    net_inflow_lag1 = (
        df["net_inflow_lag_1"]
        if "net_inflow_lag_1" in df.columns
        else df.groupby("category")["net_inflow_cr"].shift(1)
    )
    df["flow_to_aum_pct_lag_1"] = (
        net_inflow_lag1 / df["aum_lag_1"] * 100.0
    ).round(2)
    
    # Mobilisation to redemption ratio (ratio > 1 indicates expansion, < 1 indicates contraction)
    df["mob_to_red_ratio_lag_1"] = (
        df["funds_mobilised_lag_1"] / (df["redemption_lag_1"] + 1e-6)
    ).round(3)
    
    return df


def add_cross_category_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate cross-category peer indicators (Liquid vs. Overnight substitution).
    
    For Liquid Fund, peer is Overnight Fund (lagged by 1 month).
    For Overnight Fund, peer is Liquid Fund (lagged by 1 month).
    """
    df = df.copy()
    
    # Create pivot table of prior month's net flows and AUM
    piv_net = df.pivot(index="month", columns="category", values="net_inflow_cr").shift(1)
    piv_aum = df.pivot(index="month", columns="category", values="aum_cr").shift(1)
    
    liquid_peer_net = piv_net["Overnight Fund"].to_dict()
    liquid_peer_aum = piv_aum["Overnight Fund"].to_dict()
    
    overnight_peer_net = piv_net["Liquid Fund"].to_dict()
    overnight_peer_aum = piv_aum["Liquid Fund"].to_dict()
    
    peer_net_col = []
    peer_aum_col = []
    
    for _, row in df.iterrows():
        m = row["month"]
        cat = row["category"]
        if cat == "Liquid Fund":
            peer_net_col.append(liquid_peer_net.get(m, np.nan))
            peer_aum_col.append(liquid_peer_aum.get(m, np.nan))
        else:
            peer_net_col.append(overnight_peer_net.get(m, np.nan))
            peer_aum_col.append(overnight_peer_aum.get(m, np.nan))
            
    df["peer_net_inflow_lag_1"] = peer_net_col
    df["peer_aum_lag_1"] = peer_aum_col
    
    return df


def add_external_macro_features(
    df: pd.DataFrame,
    external_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Merge macroeconomic factors (RBI repo rate and Nifty 50 equity return).
    
    LEAKAGE PREVENTION:
    All external macro features are strictly lagged by 1 month. At forecast origin t,
    the model uses macroeconomic state at the close of month t-1.
    """
    df = df.copy()
    
    if external_df is None:
        ext_path = os.path.join("data", "processed", "external_factors_monthly.csv")
        if os.path.exists(ext_path):
            external_df = pd.read_csv(ext_path)
        else:
            logger.info("External factors CSV not found; building dataset...")
            external_df = build_external_factors_dataset()
            
    # Sort external by month
    ext = external_df.sort_values("month").copy()
    
    # Lag external macro indicators so month t receives month t-1 values
    ext["repo_rate_lag_1"] = ext["repo_rate_pct"].shift(1)
    ext["repo_rate_change_bps_lag_1"] = ext["repo_rate_change_bps"].shift(1)
    ext["is_rate_hike_cycle_lag_1"] = ext["is_rate_hike_cycle"].shift(1)
    ext["is_rate_cut_cycle_lag_1"] = ext["is_rate_cut_cycle"].shift(1)
    ext["nifty_close_lag_1"] = ext["nifty_close"].shift(1)
    ext["nifty_return_pct_lag_1"] = ext["nifty_return_pct"].shift(1)
    ext["nifty_return_roll_3"] = ext["nifty_return_pct"].shift(1).rolling(3).mean().round(2)
    
    macro_cols = [
        "month",
        "repo_rate_lag_1",
        "repo_rate_change_bps_lag_1",
        "is_rate_hike_cycle_lag_1",
        "is_rate_cut_cycle_lag_1",
        "nifty_close_lag_1",
        "nifty_return_pct_lag_1",
        "nifty_return_roll_3",
    ]
    
    df = pd.merge(df, ext[macro_cols], on="month", how="left")
    return df


def build_feature_pipeline(
    fund_flows_df: Optional[pd.DataFrame] = None,
    external_df: Optional[pd.DataFrame] = None,
    save_processed: bool = True,
    output_path: str = DEFAULT_OUTPUT_CSV
) -> pd.DataFrame:
    """
    Execute full feature engineering pipeline sequentially.
    
    1. Loads processed fund flows data.
    2. Adds calendar and tax features.
    3. Adds autoregressive lags (1, 2, 3, 6, 12).
    4. Adds rolling window metrics (3, 6, 12 months) computed on shifted data.
    5. Adds gross flow churn and AUM scaling ratios.
    6. Adds cross-category peer features.
    7. Adds lagged external macro features (RBI Repo & Nifty 50).
    8. Flags warmup period rows (first 12 months with NaNs from 12-month lag).
    9. Optionally saves processed feature dataset.
    """
    if fund_flows_df is None:
        if not os.path.exists(DEFAULT_INPUT_CSV):
            raise FileNotFoundError(f"Fund flows dataset not found at {DEFAULT_INPUT_CSV}")
        fund_flows_df = pd.read_csv(DEFAULT_INPUT_CSV)
        
    logger.info("Starting feature engineering on %d records...", len(fund_flows_df))
    
    # 1. Calendar
    df = add_calendar_features(fund_flows_df)
    
    # 2. Autoregressive lags
    df = add_autoregressive_lags(df)
    
    # 3. Rolling window statistics
    df = add_rolling_features(df)
    
    # 4. Gross flow & AUM features
    df = add_gross_flow_and_aum_features(df)
    
    # 5. Cross-category features
    df = add_cross_category_features(df)
    
    # 6. External macro features
    df = add_external_macro_features(df, external_df=external_df)
    
    # 7. Warmup flag (first 12 months from 2019-04 to 2020-03 have NaNs due to lag_12)
    df["is_warmup_period"] = df["net_inflow_lag_12"].isna().astype(int)
    
    # Ensure sorted order: category, month
    df = df.sort_values(by=["category", "month"]).reset_index(drop=True)
    
    if save_processed:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info("Saved featured dataset to %s (%d rows, %d columns)", output_path, len(df), len(df.columns))
        
    return df


def get_model_ready_data(
    df: Optional[pd.DataFrame] = None,
    drop_warmup: bool = True
) -> pd.DataFrame:
    """
    Retrieve feature dataset ready for predictive modeling and backtesting.
    
    If drop_warmup=True, filters out initial warmup months (first 12 months),
    ensuring 100% complete features across all columns with zero NaNs.
    """
    if df is None:
        if not os.path.exists(DEFAULT_OUTPUT_CSV):
            df = build_feature_pipeline()
        else:
            df = pd.read_csv(DEFAULT_OUTPUT_CSV)
            
    if drop_warmup:
        clean_df = df[df["is_warmup_period"] == 0].copy()
        clean_df = clean_df.reset_index(drop=True)
        return clean_df
        
    return df.copy()


def get_feature_manifest() -> Dict[str, Dict[str, Any]]:
    """
    Return comprehensive feature manifest detailing formulas, types, rationale, and leakage rules.
    """
    return {
        "calendar": {
            "month_num": "Calendar month (1 to 12). Used for monthly seasonality.",
            "quarter": "Calendar quarter (1 to 4).",
            "is_quarter_end": "Binary (1 for March, June, September, December). Captures corporate balance sheet window dressing.",
            "is_fy_end": "Binary (1 for March). Captures Indian fiscal year-end book closing.",
            "is_advance_tax_month": "Binary (1 for Mar/Jun/Sep/Dec). Captures advance corporate tax drain.",
            "is_post_quarter_month": "Binary (1 for Apr/Jul/Oct/Jan). Captures post-quarter liquidity rebound.",
            "days_in_month": "Exact number of days in the month (including leap years 2020, 2024).",
            "sin_month / cos_month": "Cyclical trigonometric encoding preserving continuity across year-end."
        },
        "autoregressive_lags": {
            "net_inflow_lag_1": "Target net flow at t-1 (INR Cr).",
            "net_inflow_lag_2": "Target net flow at t-2 (INR Cr).",
            "net_inflow_lag_3": "Target net flow at t-3 (INR Cr).",
            "net_inflow_lag_6": "Target net flow at t-6 (INR Cr). Semi-annual momentum.",
            "net_inflow_lag_12": "Target net flow at t-12 (INR Cr). Same month last year (annual seasonality)."
        },
        "rolling_statistics": {
            "net_inflow_roll_mean_3 / std_3": "Trailing 3-month mean & std computed strictly on lag 1 (no leakage).",
            "net_inflow_roll_mean_6 / std_6": "Trailing 6-month mean & std computed strictly on lag 1.",
            "net_inflow_roll_mean_12 / std_12": "Trailing 12-month mean & std computed strictly on lag 1.",
            "net_inflow_roll_min_3 / max_3": "Trailing 3-month min and max values."
        },
        "churn_and_aum": {
            "funds_mobilised_lag_1": "Gross subscriptions at t-1 (INR Cr).",
            "redemption_lag_1": "Gross repurchases at t-1 (INR Cr).",
            "churn_ratio_lag_1": "(Mobilised + Redemption) / (2 * AUM) at t-1. Measures portfolio velocity.",
            "mob_to_red_ratio_lag_1": "Mobilisation / Redemption ratio at t-1. Expansion (>1) or contraction (<1).",
            "aum_lag_1": "Month-end AUM at t-1 (INR Cr). Scale indicator.",
            "avg_aum_lag_1": "Average AUM during month t-1 (INR Cr).",
            "aum_growth_mom_lag_1": "Month-over-month AUM growth % at t-1.",
            "flow_to_aum_pct_lag_1": "Net inflow as % of total AUM at t-1."
        },
        "peer_dynamics": {
            "peer_net_inflow_lag_1": "Net flow of the other fund category at t-1 (INR Cr).",
            "peer_aum_lag_1": "AUM of the other fund category at t-1 (INR Cr)."
        },
        "macroeconomic_factors": {
            "repo_rate_lag_1": "RBI policy repo rate (% p.a.) prevailing at t-1.",
            "repo_rate_change_bps_lag_1": "Month-over-month repo rate change in basis points at t-1.",
            "is_rate_hike_cycle_lag_1": "Binary (1 if repo rate was raised at t-1).",
            "is_rate_cut_cycle_lag_1": "Binary (1 if repo rate was lowered at t-1).",
            "nifty_close_lag_1": "Nifty 50 month-end index level at t-1.",
            "nifty_return_pct_lag_1": "Nifty 50 month-over-month percentage return at t-1.",
            "nifty_return_roll_3": "Trailing 3-month rolling average equity return."
        }
    }
