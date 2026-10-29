"""
Targeted Financial-Calculation Audit & Regression Test Suite for FINHYPE.

Validates Requirements A through G:
A. Each monthly lower bound uses a point forecast and error quantile from the intended matching model/category/horizon.
B. The production cumulative-deficit calculation reproduces a manually calculated example.
C. The final recommendation is the maximum of the operational floor and peak cumulative deficit.
D. The percentage of AUM is calculated correctly across multiple scales.
E. The dashboard and service return identical recommendations for every supported category, horizon, and risk profile.
F. A change in the selected model or corresponding error quantile is reflected correctly in the recommendation.
G. The tests fail if the production function accidentally mixes model-specific point forecasts and error pools.
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd
import pytest

from app.services.cash_buffer import (
    BufferRecommendation,
    calculate_cash_buffer_recommendation,
    get_default_base_buffer_pct,
    get_preferred_model,
)
from app.services.forward_forecasting import (
    FORWARD_RESULTS_PATH,
    get_forward_recommendation,
    load_calibrator_from_backtest,
    validate_point_forecast_and_interval_compatibility,
)


# =============================================================================
# ITEM A: POINT FORECAST AND ERROR QUANTILE MATCHING INTEGRITY
# =============================================================================

def test_regression_item_a_monthly_lower_bounds_matching_model_category_horizon():
    """
    Verify each monthly lower bound in the forward projection artifact uses a point forecast
    and empirical error quantile strictly from the intended matching (category, model, horizon).
    """
    df_fwd = pd.read_csv(FORWARD_RESULTS_PATH)
    calibrator = load_calibrator_from_backtest()
    origin_month = "2026-09"

    for _, row in df_fwd.iterrows():
        cat = row["category"]
        model = row["model_name"]
        h = int(row["horizon"])
        pred_val = float(row["predicted_cr"])
        lb_80 = float(row["lower_80"])
        lb_95 = float(row["lower_95"])

        # Retrieve verified historical OOS errors for this exact tuple
        oos_errors = calibrator.get_available_oos_errors(cat, model, h, origin_month)
        assert len(oos_errors) == 24, f"Expected 24 genuine OOS errors for ({cat}, {model}, {h}), got {len(oos_errors)}"

        # Compute empirical quantiles strictly from this model's error pool
        expected_q10 = float(np.percentile(oos_errors, 10.0))
        expected_q025 = float(np.percentile(oos_errors, 2.5))

        expected_lb80 = round(pred_val + expected_q10, 2)
        expected_lb95 = round(pred_val + expected_q025, 2)

        # Enforce exact match within rounding tolerance
        assert pytest.approx(lb_80, abs=0.01) == expected_lb80, (
            f"Lower bound 80 mismatch for {cat}/{model}/h={h}: artifact={lb_80}, expected={expected_lb80}"
        )
        assert pytest.approx(lb_95, abs=0.01) == expected_lb95, (
            f"Lower bound 95 mismatch for {cat}/{model}/h={h}: artifact={lb_95}, expected={expected_lb95}"
        )


# =============================================================================
# ITEM B: MANUAL CUMULATIVE DEFICIT REPRODUCTION
# =============================================================================

def test_regression_item_b_manual_deficit_calculation_reproduction():
    """
    Verify that the production cumulative-deficit calculation reproduces a manually calculated
    synthetic example pencil-and-paper trace.
    
    Setup:
    - Current AUM = 50,000.0 Cr
    - Base buffer = 3.0% -> Base operational floor = 1,500.0 Cr
    - 3-Month horizon
    - Monthly Forecasts: [-2000.0, +1000.0, -4000.0]
    - Monthly Lower Bounds: [-5000.0, -1000.0, -6000.0]
    
    Manual Trace:
    - Step 1:
        Lower Bound = -5,000.0 Cr
        Cumulative Downside = -5,000.0 Cr
        Cumulative Deficit = max(0, -(-5000)) = 5,000.0 Cr
    - Step 2:
        Lower Bound = -1,000.0 Cr
        Cumulative Downside = -5,000.0 + (-1,000.0) = -6,000.0 Cr
        Cumulative Deficit = max(0, -(-6000)) = 6,000.0 Cr
    - Step 3:
        Lower Bound = -6,000.0 Cr
        Cumulative Downside = -6,000.0 + (-6,000.0) = -12,000.0 Cr
        Cumulative Deficit = max(0, -(-12000)) = 12,000.0 Cr
    - Peak Deficit = max(5000, 6000, 12000) = 12,000.0 Cr
    - Final Recommended Buffer = max(Base Floor 1500, Peak Deficit 12000) = 12,000.0 Cr
    - Recommended % of AUM = (12,000 / 50,000) * 100 = 24.0%
    """
    rec = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=3,
        forecast_flows=[-2000.0, 1000.0, -4000.0],
        lower_bounds=[-5000.0, -1000.0, -6000.0],
        current_aum=50000.0,
        base_buffer_pct=3.0,
        risk_tolerance="moderate",
    )

    assert rec.base_operational_buffer_cr == 1500.0
    assert rec.cumulative_downside_deficit_cr == 12000.0
    assert rec.recommended_buffer_cr == 12000.0
    assert rec.recommended_buffer_pct_aum == 24.0
    assert rec.cumulative_point_forecast_cr == -5000.0

    breakdown = rec.monthly_breakdown
    assert len(breakdown) == 3

    assert breakdown[0]["month_step"] == 1
    assert breakdown[0]["lower_bound_cr"] == -5000.0
    assert breakdown[0]["cumulative_downside_cr"] == -5000.0
    assert breakdown[0]["cumulative_deficit_cr"] == 5000.0

    assert breakdown[1]["month_step"] == 2
    assert breakdown[1]["lower_bound_cr"] == -1000.0
    assert breakdown[1]["cumulative_downside_cr"] == -6000.0
    assert breakdown[1]["cumulative_deficit_cr"] == 6000.0

    assert breakdown[2]["month_step"] == 3
    assert breakdown[2]["lower_bound_cr"] == -6000.0
    assert breakdown[2]["cumulative_downside_cr"] == -12000.0
    assert breakdown[2]["cumulative_deficit_cr"] == 12000.0


# =============================================================================
# ITEM C: FINAL RECOMMENDATION MAX(OPERATIONAL FLOOR, PEAK DEFICIT)
# =============================================================================

def test_regression_item_c_max_operational_floor_and_peak_deficit():
    """
    Verify the final buffer recommendation strictly satisfies:
    Recommended Buffer = max(Base Operational Buffer, Peak Cumulative Downside Deficit)
    """
    # Case 1: Operational floor dominates (Deficit < Floor)
    rec_floor = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=2,
        forecast_flows=[10000.0, 15000.0],
        lower_bounds=[2000.0, 3000.0],  # Positive inflows in downside
        current_aum=100000.0,
        base_buffer_pct=5.0,  # Floor = 5,000 Cr
    )
    assert rec_floor.cumulative_downside_deficit_cr == 0.0
    assert rec_floor.base_operational_buffer_cr == 5000.0
    assert rec_floor.recommended_buffer_cr == 5000.0
    assert rec_floor.recommended_buffer_cr == max(
        rec_floor.base_operational_buffer_cr, rec_floor.cumulative_downside_deficit_cr
    )

    # Case 2: Peak deficit dominates (Deficit > Floor)
    rec_deficit = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=2,
        forecast_flows=[-5000.0, -10000.0],
        lower_bounds=[-8000.0, -12000.0],
        current_aum=100000.0,
        base_buffer_pct=5.0,  # Floor = 5,000 Cr, Deficit = 20,000 Cr
    )
    assert rec_deficit.cumulative_downside_deficit_cr == 20000.0
    assert rec_deficit.base_operational_buffer_cr == 5000.0
    assert rec_deficit.recommended_buffer_cr == 20000.0
    assert rec_deficit.recommended_buffer_cr == max(
        rec_deficit.base_operational_buffer_cr, rec_deficit.cumulative_downside_deficit_cr
    )

    # Case 3: Exact boundary tie (Deficit == Floor)
    rec_tie = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=1,
        forecast_flows=[-3000.0],
        lower_bounds=[-5000.0],
        current_aum=100000.0,
        base_buffer_pct=5.0,  # Floor = 5,000 Cr, Deficit = 5,000 Cr
    )
    assert rec_tie.cumulative_downside_deficit_cr == 5000.0
    assert rec_tie.base_operational_buffer_cr == 5000.0
    assert rec_tie.recommended_buffer_cr == 5000.0


# =============================================================================
# ITEM D: AUM PERCENTAGE CALCULATION PRECISION
# =============================================================================

def test_regression_item_d_percentage_of_aum_precision():
    """Verify that buffer as a percentage of AUM is computed with exact rounding across scales."""
    test_scales = [
        (10000.0, [-2000.0], [-2500.0], 5.0),
        (84032.57, [-10000.0], [-15000.0], 2.5),
        (500000.0, [2000.0], [500.0], 3.0),
        (1234567.89, [-50000.0], [-75000.0], 1.5),
    ]

    for aum, flows, lbs, base_pct in test_scales:
        rec = calculate_cash_buffer_recommendation(
            category="Liquid Fund",
            horizon_months=len(flows),
            forecast_flows=flows,
            lower_bounds=lbs,
            current_aum=aum,
            base_buffer_pct=base_pct,
        )
        expected_pct = round((rec.recommended_buffer_cr / aum) * 100.0, 2)
        assert rec.recommended_buffer_pct_aum == expected_pct


# =============================================================================
# ITEM E: DASHBOARD AND SERVICE PARITY ACROSS ALL CONFIGURATIONS
# =============================================================================

def test_regression_item_e_dashboard_service_consistency_all_permutations():
    """
    Verify that the dashboard and service return identical recommendations
    for all 12 combinations of category, horizon, and risk profile.
    """
    df_fwd = pd.read_csv(FORWARD_RESULTS_PATH)

    categories = ["Liquid Fund", "Overnight Fund"]
    horizons = [1, 2, 3]
    risk_profiles = ["moderate", "conservative"]

    for cat in categories:
        for h in horizons:
            for risk in risk_profiles:
                # Execution path 1: Directly through service with preloaded artifact (dashboard path)
                rec_dash = get_forward_recommendation(
                    category=cat,
                    horizon_months=h,
                    risk_tolerance=risk,
                    forward_df=df_fwd,
                )

                # Execution path 2: Through service loading artifact from disk (standalone path)
                rec_serv = get_forward_recommendation(
                    category=cat,
                    horizon_months=h,
                    risk_tolerance=risk,
                )

                assert rec_dash.recommended_buffer_cr == rec_serv.recommended_buffer_cr
                assert rec_dash.recommended_buffer_pct_aum == rec_serv.recommended_buffer_pct_aum
                assert rec_dash.cumulative_downside_deficit_cr == rec_serv.cumulative_downside_deficit_cr
                assert rec_dash.preferred_model == rec_serv.preferred_model
                assert rec_dash.confidence_level_pct == rec_serv.confidence_level_pct
                assert len(rec_dash.monthly_breakdown) == len(rec_serv.monthly_breakdown)


# =============================================================================
# ITEM F: MODEL AND QUANTILE SENSITIVITY VERIFICATION
# =============================================================================

def test_regression_item_f_sensitivity_to_model_and_error_quantile_changes():
    """
    Verify that changing the selected model or error quantile is reflected correctly
    in the final recommendation.
    
    Validates:
    1. Single-Model Trajectory vs Step-Wise Stitched Trajectory for Overnight Fund.
    2. Moderate (80% / q10) vs Conservative (95% / q025) risk profile sensitivity.
    3. Standalone 1-Month Horizon (SARIMAX) recommendation.
    """
    # 1. Overnight Fund Horizon 1 Standalone (SARIMAX champion)
    rec_h1_mod = get_forward_recommendation("Overnight Fund", horizon_months=1, risk_tolerance="moderate")
    rec_h1_cons = get_forward_recommendation("Overnight Fund", horizon_months=1, risk_tolerance="conservative")
    assert rec_h1_mod.preferred_model == "sarimax"
    assert pytest.approx(rec_h1_mod.recommended_buffer_cr, abs=0.01) == 10366.04
    assert rec_h1_mod.recommended_buffer_pct_aum == 12.34
    assert pytest.approx(rec_h1_cons.recommended_buffer_cr, abs=0.01) == 17606.86
    assert rec_h1_cons.recommended_buffer_pct_aum == 20.95

    # 2. Overnight Fund Horizon 3 Single-Model Trajectory (Seasonal-Naive champion)
    rec_h3_single_mod = get_forward_recommendation(
        "Overnight Fund", horizon_months=3, risk_tolerance="moderate", step_wise_preferred=False
    )
    rec_h3_single_cons = get_forward_recommendation(
        "Overnight Fund", horizon_months=3, risk_tolerance="conservative", step_wise_preferred=False
    )
    assert rec_h3_single_mod.preferred_model == "seasonal_naive"
    assert pytest.approx(rec_h3_single_mod.recommended_buffer_cr, abs=0.01) == 74130.35
    assert rec_h3_single_mod.recommended_buffer_pct_aum == 88.22
    assert pytest.approx(rec_h3_single_cons.recommended_buffer_cr, abs=0.01) == 118049.89
    assert rec_h3_single_cons.recommended_buffer_pct_aum == 140.48

    # 3. Overnight Fund Horizon 3 Step-Wise Stitched Trajectory (SARIMAX + Seasonal-Naive + Seasonal-Naive)
    rec_h3_stitch_mod = get_forward_recommendation(
        "Overnight Fund", horizon_months=3, risk_tolerance="moderate", step_wise_preferred=True
    )
    rec_h3_stitch_cons = get_forward_recommendation(
        "Overnight Fund", horizon_months=3, risk_tolerance="conservative", step_wise_preferred=True
    )
    assert rec_h3_stitch_mod.preferred_model == "sarimax+seasonal_naive+seasonal_naive"
    assert pytest.approx(rec_h3_stitch_mod.recommended_buffer_cr, abs=0.01) == 90640.30
    assert rec_h3_stitch_mod.recommended_buffer_pct_aum == 107.86
    assert pytest.approx(rec_h3_stitch_cons.recommended_buffer_cr, abs=0.01) == 129620.28
    assert rec_h3_stitch_cons.recommended_buffer_pct_aum == 154.25

    # Strict monotonicity: Conservative must strictly exceed Moderate
    assert rec_h3_single_cons.recommended_buffer_cr > rec_h3_single_mod.recommended_buffer_cr
    assert rec_h3_stitch_cons.recommended_buffer_cr > rec_h3_stitch_mod.recommended_buffer_cr


# =============================================================================
# ITEM G: ACCIDENTAL MODEL-QUANTILE MIXING REJECTION
# =============================================================================

def test_regression_item_g_rejection_of_mixed_model_forecasts_and_error_pools():
    """
    Verify that the system detects and rejects any accidental mixing of model-specific
    point forecasts and error pools.
    """
    df_clean = pd.read_csv(FORWARD_RESULTS_PATH)

    # 1. Clean dataset passes validation
    validate_point_forecast_and_interval_compatibility(df_clean)

    # 2. Corrupt dataset with inverted interval bounds (l95 > l80)
    df_corrupt_bounds = df_clean.copy()
    idx_target = df_corrupt_bounds[
        (df_corrupt_bounds["category"] == "Overnight Fund") &
        (df_corrupt_bounds["model_name"] == "sarimax") &
        (df_corrupt_bounds["horizon"] == 1)
    ].index[0]
    df_corrupt_bounds.loc[idx_target, "lower_95"] = 10000.0  # violates l95 <= l80

    with pytest.raises(ValueError, match="Interval bounds ordering violation"):
        validate_point_forecast_and_interval_compatibility(df_corrupt_bounds)

    with pytest.raises(ValueError, match="Interval bounds ordering violation"):
        get_forward_recommendation("Overnight Fund", horizon_months=1, forward_df=df_corrupt_bounds)

    # 3. Corrupt dataset with point forecast outside bounds (mixing forecast from one model with bounds of another)
    df_mixed = df_clean.copy()
    # Replace SARIMAX h=1 point forecast with a value far outside its interval
    df_mixed.loc[idx_target, "predicted_cr"] = 999999.0
    with pytest.raises(ValueError, match="Point forecast .* falls outside calibrated bounds"):
        validate_point_forecast_and_interval_compatibility(df_mixed)

    with pytest.raises(ValueError, match="Point forecast .* falls outside calibrated bounds"):
        get_forward_recommendation("Overnight Fund", horizon_months=1, forward_df=df_mixed)

    # 4. Duplicate keys rejection
    df_dups = pd.concat([df_clean, df_clean.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate .* entries detected"):
        validate_point_forecast_and_interval_compatibility(df_dups)

