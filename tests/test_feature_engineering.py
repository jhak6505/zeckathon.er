"""
Unit tests for app.forecasting.feature_engineering module.

Validates:
1. Chronological order and sorting integrity.
2. Accurate lag calculations and category isolation.
3. Leakage prevention in rolling windows and lags.
4. Deterministic calendar and corporate advance tax indicators.
5. Cross-category peer calculations.
6. Alignment with external macroeconomic indicators.
7. Model-ready data cleanliness (zero NaNs in post-warmup rows).
8. Invariance of past features to future data updates (strict leakage check).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.forecasting.feature_engineering import (
    add_autoregressive_lags,
    add_calendar_features,
    add_cross_category_features,
    add_external_macro_features,
    add_gross_flow_and_aum_features,
    add_rolling_features,
    build_feature_pipeline,
    get_feature_manifest,
    get_model_ready_data,
)


@pytest.fixture
def sample_fund_flows_df() -> pd.DataFrame:
    """Fixture returning the processed fund flows dataset."""
    df = pd.read_csv("data/processed/fund_flows_monthly.csv")
    return df


def test_calendar_features(sample_fund_flows_df):
    """Test calendar indicators, quarter-ends, FY-end, and leap years."""
    df = add_calendar_features(sample_fund_flows_df)
    
    # Check columns exist
    for col in [
        "calendar_year", "calendar_month", "quarter", "days_in_month",
        "is_advance_tax_month", "is_quarter_end", "is_fy_end", "is_post_quarter_month",
        "sin_month", "cos_month"
    ]:
        assert col in df.columns
        
    # Check quarter ends (months 3, 6, 9, 12)
    assert set(df[df["is_quarter_end"] == 1]["calendar_month"].unique()) == {3, 6, 9, 12}
    assert set(df[df["is_quarter_end"] == 0]["calendar_month"].unique()) == {1, 2, 4, 5, 7, 8, 10, 11}
    
    # Check FY end is strictly March (month 3)
    assert set(df[df["is_fy_end"] == 1]["calendar_month"].unique()) == {3}
    
    # Check post-quarter rebound months (1, 4, 7, 10)
    assert set(df[df["is_post_quarter_month"] == 1]["calendar_month"].unique()) == {1, 4, 7, 10}
    
    # Check leap years for February: 2020 and 2024 have 29 days; 2021, 2022, 2023, 2025 have 28 days
    feb_2020 = df[(df["calendar_year"] == 2020) & (df["calendar_month"] == 2)].iloc[0]
    feb_2021 = df[(df["calendar_year"] == 2021) & (df["calendar_month"] == 2)].iloc[0]
    feb_2024 = df[(df["calendar_year"] == 2024) & (df["calendar_month"] == 2)].iloc[0]
    assert feb_2020["days_in_month"] == 29
    assert feb_2021["days_in_month"] == 28
    assert feb_2024["days_in_month"] == 29
    
    # Check trigonometric cyclics bounded in [-1, 1]
    assert df["sin_month"].between(-1.0, 1.0).all()
    assert df["cos_month"].between(-1.0, 1.0).all()


def test_autoregressive_lags_accuracy(sample_fund_flows_df):
    """Verify lags match exact prior values and do not cross category boundaries."""
    df = add_autoregressive_lags(sample_fund_flows_df, lags=[1, 2, 3, 12])
    
    for cat in ["Liquid Fund", "Overnight Fund"]:
        sub = df[df["category"] == cat].sort_values("month").reset_index(drop=True)
        
        # Row 0 must be NaN for lag 1
        assert np.isnan(sub.loc[0, "net_inflow_lag_1"])
        
        # Row 1 lag_1 must match Row 0 target
        assert sub.loc[1, "net_inflow_lag_1"] == sub.loc[0, "net_inflow_cr"]
        
        # Row 2 lag_2 must match Row 0 target
        assert sub.loc[2, "net_inflow_lag_2"] == sub.loc[0, "net_inflow_cr"]
        
        # Row 12 lag_12 must match Row 0 target
        assert sub.loc[12, "net_inflow_lag_12"] == sub.loc[0, "net_inflow_cr"]


def test_rolling_statistics_leakage_prevention(sample_fund_flows_df):
    """
    Verify rolling statistics are calculated on shifted values and strictly exclude current month.
    """
    df = add_rolling_features(sample_fund_flows_df, windows=[3, 6])
    
    for cat in ["Liquid Fund", "Overnight Fund"]:
        sub = df[df["category"] == cat].sort_values("month").reset_index(drop=True)
        
        # Rows 0, 1, 2 must have NaN for roll_mean_3 because it needs 3 prior months (t-1, t-2, t-3)
        assert np.isnan(sub.loc[0, "net_inflow_roll_mean_3"])
        assert np.isnan(sub.loc[1, "net_inflow_roll_mean_3"])
        assert np.isnan(sub.loc[2, "net_inflow_roll_mean_3"])
        
        # Row 3 must be the average of Row 0, Row 1, and Row 2 net flows
        expected_roll3 = (sub.loc[0, "net_inflow_cr"] + sub.loc[1, "net_inflow_cr"] + sub.loc[2, "net_inflow_cr"]) / 3.0
        assert pytest.approx(sub.loc[3, "net_inflow_roll_mean_3"], rel=1e-5) == expected_roll3
        
        # Crucial leakage test: row 3's rolling mean must NOT include row 3's own net flow!
        assert sub.loc[3, "net_inflow_roll_mean_3"] != sub.loc[3, "net_inflow_cr"]


def test_category_isolation(sample_fund_flows_df):
    """Verify Liquid and Overnight calculations do not contaminate each other."""
    df = add_autoregressive_lags(sample_fund_flows_df, lags=[1])
    
    liq = df[df["category"] == "Liquid Fund"].sort_values("month").reset_index(drop=True)
    ovn = df[df["category"] == "Overnight Fund"].sort_values("month").reset_index(drop=True)
    
    # Liquid lag 1 at index 1 must equal Liquid net flow at index 0, not Overnight
    assert liq.loc[1, "net_inflow_lag_1"] == liq.loc[0, "net_inflow_cr"]
    assert liq.loc[1, "net_inflow_lag_1"] != ovn.loc[0, "net_inflow_cr"]
    
    # Overnight lag 1 at index 1 must equal Overnight net flow at index 0, not Liquid
    assert ovn.loc[1, "net_inflow_lag_1"] == ovn.loc[0, "net_inflow_cr"]
    assert ovn.loc[1, "net_inflow_lag_1"] != liq.loc[0, "net_inflow_cr"]


def test_gross_flow_and_aum_features(sample_fund_flows_df):
    """Verify gross mobilisations, redemptions, churn ratio, and AUM growth."""
    df = add_gross_flow_and_aum_features(sample_fund_flows_df)
    
    assert "funds_mobilised_lag_1" in df.columns
    assert "redemption_lag_1" in df.columns
    assert "aum_lag_1" in df.columns
    assert "churn_ratio_lag_1" in df.columns
    assert "aum_growth_mom_lag_1" in df.columns
    assert "mob_to_red_ratio_lag_1" in df.columns
    
    # Liquid fund at index 1
    liq = df[df["category"] == "Liquid Fund"].sort_values("month").reset_index(drop=True)
    expected_churn = (liq.loc[0, "funds_mobilised_cr"] + liq.loc[0, "redemption_cr"]) / (2 * liq.loc[0, "aum_cr"])
    assert pytest.approx(liq.loc[1, "churn_ratio_lag_1"], abs=1e-2) == expected_churn


def test_cross_category_peer_features(sample_fund_flows_df):
    """Verify cross-category peer net flows and AUM are strictly lagged by 1 month."""
    df = add_cross_category_features(sample_fund_flows_df)
    
    liq = df[df["category"] == "Liquid Fund"].sort_values("month").reset_index(drop=True)
    ovn = df[df["category"] == "Overnight Fund"].sort_values("month").reset_index(drop=True)
    
    # Month 0: both peers should be NaN
    assert np.isnan(liq.loc[0, "peer_net_inflow_lag_1"])
    assert np.isnan(ovn.loc[0, "peer_net_inflow_lag_1"])
    
    # Month 1 (2019-05): Liquid's peer net flow must match Overnight's 2019-04 net flow
    assert liq.loc[1, "peer_net_inflow_lag_1"] == ovn.loc[0, "net_inflow_cr"]
    # Month 1 (2019-05): Overnight's peer net flow must match Liquid's 2019-04 net flow
    assert ovn.loc[1, "peer_net_inflow_lag_1"] == liq.loc[0, "net_inflow_cr"]


def test_external_macro_features(sample_fund_flows_df):
    """Verify external factors merge and are strictly lagged by 1 month."""
    df = add_external_macro_features(sample_fund_flows_df)
    
    assert "repo_rate_lag_1" in df.columns
    assert "nifty_close_lag_1" in df.columns
    assert "nifty_return_pct_lag_1" in df.columns
    
    # Check that repo rate at 2019-05 receives 2019-04 rate (6.00%)
    sub_may_19 = df[df["month"] == "2019-05"]
    assert (sub_may_19["repo_rate_lag_1"] == 6.00).all()


def test_leakage_invariance_future_data(sample_fund_flows_df):
    """
    CRITICAL LEAKAGE TEST:
    Modifying or appending future data must NOT change past feature values.
    """
    # 1. Compute features on dataset truncated at 2024-12
    df_trunc = sample_fund_flows_df[sample_fund_flows_df["month"] <= "2024-12"].copy()
    features_trunc = build_feature_pipeline(fund_flows_df=df_trunc, save_processed=False)
    
    # 2. Compute features on full dataset (up to 2026-09)
    features_full = build_feature_pipeline(fund_flows_df=sample_fund_flows_df, save_processed=False)
    
    # Filter features_full to months <= 2024-12
    features_full_sub = features_full[features_full["month"] <= "2024-12"].copy()
    
    # Assert numerical columns for all past months are completely identical
    numeric_cols = features_trunc.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        s1 = features_trunc[col].fillna(-999999).to_numpy()
        s2 = features_full_sub[col].fillna(-999999).to_numpy()
        np.testing.assert_allclose(s1, s2, rtol=1e-5, atol=1e-5, err_msg=f"Leakage detected in {col}!")


def test_model_ready_data_cleanliness(sample_fund_flows_df):
    """Verify that get_model_ready_data removes warmup rows and has 0 NaNs."""
    df_featured = build_feature_pipeline(fund_flows_df=sample_fund_flows_df, save_processed=False)
    model_df = get_model_ready_data(df_featured, drop_warmup=True)
    
    # Exactly 156 rows (78 Liquid, 78 Overnight) covering 2020-04 to 2026-09
    assert len(model_df) == 156
    assert (model_df["category"] == "Liquid Fund").sum() == 78
    assert (model_df["category"] == "Overnight Fund").sum() == 78
    assert model_df["month"].min() == "2020-04"
    assert model_df["month"].max() == "2026-09"
    
    # Verify zero NaNs in model-ready dataset
    null_counts = model_df.isnull().sum()
    assert null_counts.sum() == 0, f"Nulls found: {null_counts[null_counts > 0]}"


def test_feature_manifest():
    """Verify feature manifest structure and documentation."""
    manifest = get_feature_manifest()
    assert isinstance(manifest, dict)
    assert "calendar" in manifest
    assert "autoregressive_lags" in manifest
    assert "rolling_statistics" in manifest
    assert "churn_and_aum" in manifest
    assert "peer_dynamics" in manifest
    assert "macroeconomic_factors" in manifest


def test_leakage_future_data_mutation(sample_fund_flows_df):
    """
    STRICT TIME-SERIES ANTI-LEAKAGE REGRESSION TEST:
    Mutating future target flows and AUM after a historical cutoff (2024-12) must have
    ZERO effect on engineered features computed for past time steps (<= 2024-12).
    """
    cutoff = "2024-12"
    df_base = sample_fund_flows_df.copy()
    df_mutated = sample_fund_flows_df.copy()

    # Drastically mutate future flows and balances after cutoff
    fut_mask = df_mutated["month"] > cutoff
    df_mutated.loc[fut_mask, "net_inflow_cr"] = df_mutated.loc[fut_mask, "net_inflow_cr"] * -3.5 + 99999.0
    if "funds_mobilised_cr" in df_mutated.columns:
        df_mutated.loc[fut_mask, "funds_mobilised_cr"] = df_mutated.loc[fut_mask, "funds_mobilised_cr"] * 2.5
    if "redemption_cr" in df_mutated.columns:
        df_mutated.loc[fut_mask, "redemption_cr"] = df_mutated.loc[fut_mask, "redemption_cr"] * 0.4
    if "aum_cr" in df_mutated.columns:
        df_mutated.loc[fut_mask, "aum_cr"] = df_mutated.loc[fut_mask, "aum_cr"] * 1.5

    feat_base = build_feature_pipeline(fund_flows_df=df_base, save_processed=False)
    feat_mutated = build_feature_pipeline(fund_flows_df=df_mutated, save_processed=False)

    sub_base = feat_base[feat_base["month"] <= cutoff].copy().reset_index(drop=True)
    sub_mutated = feat_mutated[feat_mutated["month"] <= cutoff].copy().reset_index(drop=True)

    numeric_cols = sub_base.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        v_base = sub_base[col].fillna(-9999999.0).to_numpy()
        v_mut = sub_mutated[col].fillna(-9999999.0).to_numpy()
        np.testing.assert_allclose(
            v_base,
            v_mut,
            rtol=1e-5,
            atol=1e-5,
            err_msg=f"Temporal leakage detected in feature '{col}' after future data mutation!",
        )

