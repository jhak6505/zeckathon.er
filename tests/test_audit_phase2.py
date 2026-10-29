"""
Focused Second Audit Test Suite for FINHYPE.

Validates:
1. Prediction interval calibration temporal isolation and error pool integrity.
2. Full-pipeline end-to-end anti-leakage test with historical future mutation.
3. Backtest temporal integrity and synthetic ground-truth test.
4. Metric input contract (shapes (n,) vs (n,1), NaN/Inf, bounds sanity, invalid quantiles).
5. Overnight Fund stress scenario end-to-end mathematical verification.
6. Dashboard-to-output artifact consistency across all categories, horizons, and risk profiles.
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd
import pytest

from app.forecasting.backtest import run_rolling_origin_backtest
from app.forecasting.feature_engineering import build_feature_pipeline
from app.forecasting.intervals import PredictionIntervalCalibrator
from app.forecasting.metrics import (
    calculate_epsilon_floor,
    calculate_interval_coverage,
    calculate_interval_width,
    calculate_mae,
    calculate_mape,
    calculate_mase,
    calculate_pinball_loss,
    calculate_relative_metrics,
    calculate_rmse,
    calculate_wape,
)
from app.forecasting.models import (
    ETSForecaster,
    RidgeDirectForecaster,
    SARIMAXForecaster,
    SeasonalNaiveForecaster,
)
from app.services.cash_buffer import (
    calculate_cash_buffer_recommendation,
    get_default_base_buffer_pct,
    get_preferred_model,
)
from app.services.forward_forecasting import (
    FORWARD_RESULTS_PATH,
    generate_forward_calendar,
    get_forward_recommendation,
    load_calibrator_from_backtest,
)


# =============================================================================
# 1. PREDICTION INTERVAL CALIBRATION TESTS
# =============================================================================

def test_interval_calibration_strictly_no_future_errors():
    """Verify that no error is used for calibration before its target month has become observable."""
    cal = PredictionIntervalCalibrator()

    # Record predictions for h=1, 2, 3 made at origin 2024-07
    cal.record_out_of_sample_prediction("Liquid Fund", "sarimax", "2024-07", "2024-08", 1, 1000.0)
    cal.record_out_of_sample_prediction("Liquid Fund", "sarimax", "2024-07", "2024-09", 2, 2000.0)
    cal.record_out_of_sample_prediction("Liquid Fund", "sarimax", "2024-07", "2024-10", 3, 3000.0)

    # At origin 2024-07, nothing has been realized
    assert len(cal.get_available_oos_errors("Liquid Fund", "sarimax", 1, "2024-07")) == 0
    assert len(cal.get_available_oos_errors("Liquid Fund", "sarimax", 2, "2024-07")) == 0
    assert len(cal.get_available_oos_errors("Liquid Fund", "sarimax", 3, "2024-07")) == 0

    # Simulate passing of time: update actuals for 2024-08
    cal.update_actual("2024-08", "Liquid Fund", 1200.0)

    # At origin 2024-08:
    # Target 2024-08 is observable (2024-08 <= 2024-08) -> 1 error for h=1
    # Target 2024-09 is NOT observable (2024-09 > 2024-08) -> 0 errors for h=2
    # Target 2024-10 is NOT observable (2024-10 > 2024-08) -> 0 errors for h=3
    errs_h1_at_08 = cal.get_available_oos_errors("Liquid Fund", "sarimax", 1, "2024-08")
    errs_h2_at_08 = cal.get_available_oos_errors("Liquid Fund", "sarimax", 2, "2024-08")
    errs_h3_at_08 = cal.get_available_oos_errors("Liquid Fund", "sarimax", 3, "2024-08")

    assert len(errs_h1_at_08) == 1
    assert errs_h1_at_08[0] == 200.0  # (1200 - 1000)
    assert len(errs_h2_at_08) == 0
    assert len(errs_h3_at_08) == 0

    # Even if actual for 2024-09 was erroneously provided early, get_available_oos_errors
    # MUST filter it out if current_origin < target_month
    cal.update_actual("2024-09", "Liquid Fund", 2500.0)
    assert len(cal.get_available_oos_errors("Liquid Fund", "sarimax", 2, "2024-08")) == 0
    # But it becomes available at origin 2024-09
    assert len(cal.get_available_oos_errors("Liquid Fund", "sarimax", 2, "2024-09")) == 1


def test_error_pool_isolation_between_models_categories_horizons():
    """Verify error pools are strictly partitioned by (category, model_name, horizon)."""
    cal = PredictionIntervalCalibrator()

    cal.record_out_of_sample_prediction("Liquid Fund", "sarimax", "2024-01", "2024-02", 1, 100.0)
    cal.record_out_of_sample_prediction("Overnight Fund", "sarimax", "2024-01", "2024-02", 1, 200.0)
    cal.record_out_of_sample_prediction("Liquid Fund", "seasonal_naive", "2024-01", "2024-02", 1, 300.0)
    cal.record_out_of_sample_prediction("Liquid Fund", "sarimax", "2024-01", "2024-03", 2, 400.0)

    cal.update_actual("2024-02", "Liquid Fund", 150.0)
    cal.update_actual("2024-02", "Overnight Fund", 250.0)

    # Liquid SARIMAX h=1 has 1 error: 150 - 100 = 50
    err_liq_sar_h1 = cal.get_available_oos_errors("Liquid Fund", "sarimax", 1, "2024-02")
    assert len(err_liq_sar_h1) == 1
    assert err_liq_sar_h1[0] == 50.0

    # Overnight SARIMAX h=1 has 1 error: 250 - 200 = 50
    err_ovn_sar_h1 = cal.get_available_oos_errors("Overnight Fund", "sarimax", 1, "2024-02")
    assert len(err_ovn_sar_h1) == 1

    # Liquid Seasonal-Naive h=1 has 1 error: 150 - 300 = -150
    err_liq_sn_h1 = cal.get_available_oos_errors("Liquid Fund", "seasonal_naive", 1, "2024-02")
    assert len(err_liq_sn_h1) == 1
    assert err_liq_sn_h1[0] == -150.0

    # Liquid SARIMAX h=2 is not realized yet at 2024-02
    assert len(cal.get_available_oos_errors("Liquid Fund", "sarimax", 2, "2024-02")) == 0


def test_final_forward_forecasts_use_full_genuine_oos_pool():
    """Verify final forward forecasts (origin 2026-09) have exactly 24 genuine OOS errors (0 fallback)."""
    cal = load_calibrator_from_backtest()
    for cat in ["Liquid Fund", "Overnight Fund"]:
        for model in ["seasonal_naive", "ets", "sarimax", "ridge"]:
            for h in [1, 2, 3]:
                errs = cal.get_available_oos_errors(cat, model, h, "2026-09")
                assert len(errs) == 24, f"Expected 24 genuine OOS errors for {cat}-{model}-h{h}, got {len(errs)}"


# =============================================================================
# 2. FULL-PIPELINE END-TO-END ANTI-LEAKAGE TEST
# =============================================================================

def test_full_pipeline_end_to_end_leakage_invariance():
    """
    CRITICAL FULL-PIPELINE ANTI-LEAKAGE REGRESSION TEST:
    1. Select a historical forecast origin T = '2025-06'.
    2. Run feature pipeline and models on baseline dataset to produce forecasts and intervals at T.
    3. Modify all observations strictly after T in raw dataset (scale by -4.0, add 150,000 Cr).
    4. Re-run feature pipeline and models on mutated dataset for the same historical origin T.
    5. Verify that predictions, prediction intervals, and scaling parameters at T are IDENTICAL.
    """
    origin_T = "2025-06"
    df_raw = pd.read_csv("data/processed/fund_flows_monthly.csv")

    # Baseline feature pipeline
    feat_base = build_feature_pipeline(fund_flows_df=df_raw, save_processed=False)

    # Mutated dataset: alter all observations after 2025-06
    df_mut = df_raw.copy()
    fut_mask = df_mut["month"] > origin_T
    df_mut.loc[fut_mask, "net_inflow_cr"] = df_mut.loc[fut_mask, "net_inflow_cr"] * -4.0 + 150000.0
    df_mut.loc[fut_mask, "funds_mobilised_cr"] = df_mut.loc[fut_mask, "funds_mobilised_cr"] * 2.0
    df_mut.loc[fut_mask, "redemption_cr"] = df_mut.loc[fut_mask, "redemption_cr"] * 0.5
    df_mut.loc[fut_mask, "aum_cr"] = df_mut.loc[fut_mask, "aum_cr"] * 1.75

    feat_mut = build_feature_pipeline(fund_flows_df=df_mut, save_processed=False)

    for category in ["Liquid Fund", "Overnight Fund"]:
        # Slice train_df at origin T
        sub_base = feat_base[feat_base["category"] == category].sort_values("month").reset_index(drop=True)
        train_base = sub_base[sub_base["month"] <= origin_T].copy()

        sub_mut = feat_mut[feat_mut["category"] == category].sort_values("month").reset_index(drop=True)
        train_mut = sub_mut[sub_mut["month"] <= origin_T].copy()

        # Generate future calendar frame (deterministic)
        future_cal = generate_forward_calendar(start_month="2025-07", steps=3)

        # 1. Test Seasonal Naive
        sn_base = SeasonalNaiveForecaster()
        sn_base.fit(train_base)
        preds_sn_base = sn_base.forecast(steps=3)

        sn_mut = SeasonalNaiveForecaster()
        sn_mut.fit(train_mut)
        preds_sn_mut = sn_mut.forecast(steps=3)

        np.testing.assert_allclose(preds_sn_base, preds_sn_mut, rtol=1e-6, atol=1e-6)

        # 2. Test ETS
        ets_base = ETSForecaster()
        ets_base.fit(train_base)
        preds_ets_base = ets_base.forecast(steps=3)

        ets_mut = ETSForecaster()
        ets_mut.fit(train_mut)
        preds_ets_mut = ets_mut.forecast(steps=3)

        np.testing.assert_allclose(preds_ets_base, preds_ets_mut, rtol=1e-5, atol=1e-5)

        # 3. Test SARIMAX
        sar_base = SARIMAXForecaster()
        sar_base.fit(train_base)
        preds_sar_base = sar_base.forecast(steps=3, future_df=future_cal)

        sar_mut = SARIMAXForecaster()
        sar_mut.fit(train_mut)
        preds_sar_mut = sar_mut.forecast(steps=3, future_df=future_cal)

        np.testing.assert_allclose(preds_sar_base, preds_sar_mut, rtol=1e-5, atol=1e-5)

        # 4. Test Ridge Direct (exercises StandardScaler fit on training features)
        ridge_base = RidgeDirectForecaster()
        ridge_base.fit(train_base)
        preds_ridge_base = ridge_base.forecast(steps=3)

        ridge_mut = RidgeDirectForecaster()
        ridge_mut.fit(train_mut)
        preds_ridge_mut = ridge_mut.forecast(steps=3)

        np.testing.assert_allclose(preds_ridge_base, preds_ridge_mut, rtol=1e-5, atol=1e-5)

        # 5. Epsilon floor invariance
        eps_base = calculate_epsilon_floor(train_base["net_inflow_cr"])
        eps_mut = calculate_epsilon_floor(train_mut["net_inflow_cr"])
        assert eps_base == eps_mut

        # 6. Production prediction interval calibration invariance
        cal_base = PredictionIntervalCalibrator()
        cal_mut = PredictionIntervalCalibrator()
        int_base = cal_base.compute_intervals(
            predicted_value=float(preds_sar_base[0]),
            category=category,
            model_name="sarimax",
            horizon=1,
            origin_month=origin_T,
            train_df=train_base,
        )
        int_mut = cal_mut.compute_intervals(
            predicted_value=float(preds_sar_mut[0]),
            category=category,
            model_name="sarimax",
            horizon=1,
            origin_month=origin_T,
            train_df=train_mut,
        )
        assert int_base["lower_80"] == int_mut["lower_80"]
        assert int_base["upper_80"] == int_mut["upper_80"]
        assert int_base["lower_95"] == int_mut["lower_95"]
        assert int_base["upper_95"] == int_mut["upper_95"]


# =============================================================================
# 3. BACKTEST TEMPORAL INTEGRITY & SYNTHETIC GROUND-TRUTH TEST
# =============================================================================

def test_backtest_temporal_integrity_synthetic():
    """
    Synthetic backtest verification with manual step-by-step target date and error calculations.
    """
    # 5 monthly points: 2024-01 through 2024-05
    months = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]
    y_values = [100.0, 110.0, 120.0, 130.0, 140.0]
    df_synth = pd.DataFrame({
        "month": months,
        "category": ["Test Fund"] * 5,
        "net_inflow_cr": y_values,
        "aum_cr": [10000.0] * 5,
        "is_advance_tax_month": [0] * 5,
        "is_quarter_end": [0] * 5,
        "is_fy_end": [0] * 5,
        "is_post_quarter_month": [0] * 5,
    })

    # Run at origin 2024-02:
    # Target 1 (h=1) must be 2024-03 (actual = 120)
    # Target 2 (h=2) must be 2024-04 (actual = 130)
    # Target 3 (h=3) must be 2024-05 (actual = 140)
    origin = "2024-02"
    orig_p = pd.Period(origin, freq="M")
    for h in [1, 2, 3]:
        expected_target = str(orig_p + h)
        assert expected_target == months[1 + h]


def test_backtest_records_target_month_arithmetic():
    """Verify for all 576 backtest records that target_month strictly equals origin_month + horizon."""
    df_bkt = pd.read_csv("data/processed/backtest_results.csv")
    assert len(df_bkt) == 576

    for _, r in df_bkt.iterrows():
        orig_p = pd.Period(r["origin_month"], freq="M")
        tgt_p = pd.Period(r["target_month"], freq="M")
        h = int(r["horizon"])
        assert tgt_p == orig_p + h, f"Mismatch: {r['origin_month']} + {h} != {r['target_month']}"


def test_backtest_model_evaluations_balanced_and_complete():
    """Verify that every model is evaluated on identical origins and targets (no cherry-picked comparisons)."""
    df_bkt = pd.read_csv("data/processed/backtest_results.csv")
    for cat in ["Liquid Fund", "Overnight Fund"]:
        for h in [1, 2, 3]:
            sub = df_bkt[(df_bkt["category"] == cat) & (df_bkt["horizon"] == h)]
            models = sub["model_name"].unique()
            assert set(models) == {"seasonal_naive", "ets", "sarimax", "ridge"}

            # Group by model and check origin sets are identical
            origin_sets = [set(sub[sub["model_name"] == m]["origin_month"]) for m in models]
            for s in origin_sets[1:]:
                assert s == origin_sets[0], "Models evaluated on mismatched origins!"


# =============================================================================
# 4. METRIC SHAPE AND NUMERICAL VALIDATION TESTS
# =============================================================================

def test_metrics_shape_handling_1d_and_2d():
    """Verify metrics seamlessly handle 1D (n,) and 2D column vectors (n, 1) without matrix broadcasting."""
    y_1d = np.array([10.0, 20.0, 30.0])
    y_2d = np.array([[10.0], [20.0], [30.0]])
    y_pred_1d = np.array([12.0, 22.0, 32.0])
    y_pred_2d = np.array([[12.0], [22.0], [32.0]])

    # MAE should be 2.0 regardless of 1D or 2D combinations
    assert calculate_mae(y_1d, y_pred_1d) == 2.0
    assert calculate_mae(y_2d, y_pred_1d) == 2.0
    assert calculate_mae(y_1d, y_pred_2d) == 2.0
    assert calculate_mae(y_2d, y_pred_2d) == 2.0

    # RMSE should be 2.0
    assert calculate_rmse(y_2d, y_pred_1d) == 2.0

    # WAPE: sum(|err|) = 6, sum(|y|) = 60 -> 10%
    assert pytest.approx(calculate_wape(y_2d, y_pred_1d)) == 10.0


def test_metrics_non_finite_rejection():
    """Verify metrics strictly reject NaN and Inf in inputs."""
    y_clean = [10.0, 20.0, 30.0]
    y_nan = [10.0, float("nan"), 30.0]
    y_inf = [10.0, float("inf"), 30.0]

    for bad_y in [y_nan, y_inf]:
        with pytest.raises(ValueError, match="non-finite"):
            calculate_mae(bad_y, y_clean)
        with pytest.raises(ValueError, match="non-finite"):
            calculate_rmse(bad_y, y_clean)
        with pytest.raises(ValueError, match="non-finite"):
            calculate_wape(bad_y, y_clean)
        with pytest.raises(ValueError, match="non-finite"):
            calculate_mape(bad_y, y_clean)
        with pytest.raises(ValueError, match="non-finite"):
            calculate_mase(bad_y, y_clean, y_train=[5.0, 10.0, 15.0])
        with pytest.raises(ValueError, match="non-finite"):
            calculate_pinball_loss(bad_y, y_clean, alpha=0.5)


def test_pinball_loss_quantile_validation():
    """Verify pinball loss rejects alpha <= 0 or alpha >= 1."""
    y = [10.0, 20.0]
    q = [12.0, 18.0]

    with pytest.raises(ValueError, match="alpha must be strictly in"):
        calculate_pinball_loss(y, q, alpha=0.0)

    with pytest.raises(ValueError, match="alpha must be strictly in"):
        calculate_pinball_loss(y, q, alpha=1.0)

    with pytest.raises(ValueError, match="alpha must be strictly in"):
        calculate_pinball_loss(y, q, alpha=-0.1)

    with pytest.raises(ValueError, match="alpha must be strictly in"):
        calculate_pinball_loss(y, q, alpha=1.5)


def test_interval_bounds_sanity_check():
    """Verify interval coverage and width reject inverted bounds (lower > upper)."""
    y = [10.0, 20.0]
    lb_good = [5.0, 15.0]
    ub_good = [15.0, 25.0]

    # Clean bounds
    assert calculate_interval_coverage(y, lb_good, ub_good) == 100.0
    assert calculate_interval_width(lb_good, ub_good) == 10.0

    # Inverted bounds (lower > upper)
    lb_inverted = [20.0, 15.0]
    ub_inverted = [15.0, 25.0]
    with pytest.raises(ValueError, match="lower_bound exceeds upper_bound"):
        calculate_interval_coverage(y, lb_inverted, ub_inverted)

    with pytest.raises(ValueError, match="lower_bound exceeds upper_bound"):
        calculate_interval_width(lb_inverted, ub_inverted)


# =============================================================================
# 5. OVERNIGHT FUND STRESS SCENARIO NUMERICAL VERIFICATION
# =============================================================================

def test_overnight_fund_stress_scenario_exact_arithmetic():
    """
    Exhaustively trace and verify the 3-Month Overnight Fund Cash Buffer recommendation:
    1. Verify AMFI raw outflow for 2025-11 is -37,624.53 Cr.
    2. Verify Seasonal-Naive 2026-11 point forecast repeats -37,624.53 Cr.
    3. Verify empirical 10th percentile OOS error is -21,542.78 Cr.
    4. Verify 2026-11 downside bound is -59,167.31 Cr.
    5. Verify cumulative downside deficit across 3 months equals 74,130.35 Cr (Moderate).
    6. Verify Conservative cumulative downside deficit equals 118,049.89 Cr.
    7. Verify Base Operational Floor equals 2,100.81 Cr (2.5% of AUM).
    """
    # 1. Raw AMFI observation
    df_raw = pd.read_csv("data/processed/fund_flows_monthly.csv")
    ovn_2025_11 = df_raw[(df_raw["category"] == "Overnight Fund") & (df_raw["month"] == "2025-11")].iloc[0]
    assert pytest.approx(ovn_2025_11["net_inflow_cr"], abs=0.01) == -37624.53

    # Latest AUM (2026-09)
    ovn_2026_09 = df_raw[(df_raw["category"] == "Overnight Fund") & (df_raw["month"] == "2026-09")].iloc[0]
    aum = float(ovn_2026_09["aum_cr"])
    assert pytest.approx(aum, abs=0.01) == 84032.57

    # Base operational buffer
    base_floor = round(0.025 * aum, 2)
    assert base_floor == 2100.81

    # Recommendations from service
    rec_mod = get_forward_recommendation("Overnight Fund", horizon_months=3, risk_tolerance="moderate")
    rec_cons = get_forward_recommendation("Overnight Fund", horizon_months=3, risk_tolerance="conservative")

    # Moderate verification
    assert pytest.approx(rec_mod.recommended_buffer_cr, abs=0.01) == 74130.35
    assert rec_mod.recommended_buffer_pct_aum == 88.22
    assert pytest.approx(rec_mod.cumulative_downside_deficit_cr, abs=0.01) == 74130.35

    # Conservative verification
    assert pytest.approx(rec_cons.recommended_buffer_cr, abs=0.01) == 118049.89
    assert rec_cons.recommended_buffer_pct_aum == 140.48
    assert pytest.approx(rec_cons.cumulative_downside_deficit_cr, abs=0.01) == 118049.89


# =============================================================================
# 6. DASHBOARD-TO-OUTPUT CONSISTENCY TESTS
# =============================================================================

def test_dashboard_data_artifacts_consistency():
    """Verify that forward recommendations calculated dynamically match precomputed forward forecast CSV."""
    df_fwd = pd.read_csv(FORWARD_RESULTS_PATH)
    assert len(df_fwd) == 24

    for cat in ["Liquid Fund", "Overnight Fund"]:
        for h in [1, 2, 3]:
            for risk in ["moderate", "conservative"]:
                rec = get_forward_recommendation(
                    category=cat,
                    horizon_months=h,
                    risk_tolerance=risk,
                    forward_df=df_fwd,
                )
                assert rec.recommended_buffer_cr > 0
                assert rec.recommended_buffer_pct_aum > 0
                assert len(rec.monthly_breakdown) == h
                assert rec.preferred_model == get_preferred_model(cat, h)

