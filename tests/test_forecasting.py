"""
Unit and integration tests for FINHYPE Phase 4 Forecasting System.

Validates:
1. Metric calculations (MAE, RMSE, WAPE, MASE, MAPE with origin-specific epsilon, Pinball Loss).
2. Model estimators (Seasonal-Naive, ETS, SARIMAX, Ridge Direct).
3. Prediction interval calibration (OOS error isolation, monotonicity, coverage logic).
4. Backtesting boundaries, origin selection, and strict anti-leakage isolation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.forecasting.backtest import (
    EVALUATION_ORIGINS,
    generate_backtest_summary,
    run_rolling_origin_backtest,
)
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
    compute_all_metrics,
)
from app.forecasting.models import (
    ETSForecaster,
    RidgeDirectForecaster,
    SARIMAXForecaster,
    SeasonalNaiveForecaster,
    get_available_models,
)


# --- 1. Metrics Tests ---

def test_mae_rmse_wape_synthetic():
    """Verify scale-dependent and scale-independent error formulas on synthetic inputs."""
    y_true = np.array([100.0, -50.0, 0.0, 200.0])
    y_pred = np.array([110.0, -40.0, 10.0, 180.0])
    # Absolute errors: 10, 10, 10, 20 -> Mean = 12.5
    assert pytest.approx(calculate_mae(y_true, y_pred), abs=1e-5) == 12.5
    
    # Squared errors: 100, 100, 100, 400 -> Mean = 175 -> Sqrt = 13.228756
    assert pytest.approx(calculate_rmse(y_true, y_pred), abs=1e-5) == np.sqrt(175.0)
    
    # WAPE: Sum(|err|) = 50, Sum(|y|) = 100 + 50 + 0 + 200 = 350 -> 50 / 350 * 100 = 14.2857%
    assert pytest.approx(calculate_wape(y_true, y_pred), abs=1e-3) == (50.0 / 350.0) * 100.0


def test_origin_specific_epsilon_floor():
    """Verify origin-specific epsilon floor uses only y_train and respects minimum floor."""
    y_train = np.array([10.0, -20.0, 30.0, 40.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0])
    # 10th percentile of |y_train| is between 10 and 20
    floor = calculate_epsilon_floor(y_train, percentile=10.0, min_floor=5.0)
    assert floor >= 10.0
    
    # Check min_floor enforcement
    floor_high_min = calculate_epsilon_floor(y_train, percentile=10.0, min_floor=500.0)
    assert floor_high_min == 500.0


def test_mape_zero_handling():
    """Verify MAPE does not explode to infinity when actual value is zero."""
    y_true = np.array([0.0, 100.0])
    y_pred = np.array([10.0, 110.0])
    epsilon = 50.0
    # For y_true=0, denom = max(0, 50) = 50; err = 10 / 50 = 0.2
    # For y_true=100, denom = max(100, 50) = 100; err = 10 / 100 = 0.1
    # Mean = (0.2 + 0.1) / 2 * 100 = 15.0%
    mape = calculate_mape(y_true, y_pred, epsilon=epsilon)
    assert pytest.approx(mape, abs=1e-5) == 15.0


def test_mase_seasonal():
    """Verify MASE uses training in-sample seasonal differences as scaling denominator."""
    # 24 training points with seasonal cycle 12
    y_train = np.concatenate([np.ones(12) * 100.0, np.ones(12) * 110.0])
    # Seasonally, difference is |110 - 100| = 10.0
    y_true = np.array([105.0])
    y_pred = np.array([100.0])  # MAE = 5.0
    # MASE = 5.0 / 10.0 = 0.5
    mase = calculate_mase(y_true, y_pred, y_train=y_train, seasonal_period=12)
    assert pytest.approx(mase, abs=1e-4) == 0.5


def test_pinball_loss_quantiles():
    """Verify pinball loss penalties for over-prediction and under-prediction."""
    y_true = np.array([100.0])
    
    # Over-prediction (q > y): diff = -10, loss = (1 - alpha) * 10
    q_high = np.array([110.0])
    loss_01 = calculate_pinball_loss(y_true, q_high, alpha=0.10)
    assert pytest.approx(loss_01, abs=1e-5) == 0.90 * 10.0
    
    # Under-prediction (q < y): diff = +10, loss = alpha * 10
    q_low = np.array([90.0])
    loss_09 = calculate_pinball_loss(y_true, q_low, alpha=0.90)
    assert pytest.approx(loss_09, abs=1e-5) == 0.90 * 10.0


def test_interval_coverage_and_width():
    """Verify interval coverage and width calculations."""
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    lower = np.array([5.0, 15.0, 35.0, 35.0])   # 10, 20, 40 covered (3 of 4)
    upper = np.array([15.0, 25.0, 45.0, 45.0])
    
    cov = calculate_interval_coverage(y_true, lower, upper)
    assert cov == 75.0
    
    width = calculate_interval_width(lower, upper)
    assert width == 10.0


def test_relative_metrics():
    """Verify relative MAE and skill score against baseline."""
    rel = calculate_relative_metrics(mae_model=80.0, mae_baseline=100.0)
    assert rel["rel_mae"] == 0.8
    assert rel["skill_score"] == 0.2


# --- 2. Model Estimator Tests ---

def test_seasonal_naive_forecaster():
    """Verify seasonal naive persists exact 12-month prior values."""
    s_naive = SeasonalNaiveForecaster()
    # 24 months of synthetic data
    history = [float(i) for i in range(24)]
    df = pd.DataFrame({"month": [f"2020-{m:02d}" for m in range(1, 25)], "net_inflow_cr": history})
    s_naive.fit(df)
    preds = s_naive.forecast(steps=3)
    # Target 25 should persist month 25 - 12 = 13 (index 12)
    assert preds[0] == history[12]
    # Target 26 should persist month 26 - 12 = 14 (index 13)
    assert preds[1] == history[13]
    # Target 27 should persist month 27 - 12 = 15 (index 14)
    assert preds[2] == history[14]


def test_ets_forecaster():
    """Verify additive ETS fits and forecasts without error on negative values."""
    ets = ETSForecaster()
    # 36 months of data with seasonal pattern and negative values
    months = [f"2020-{i:02d}" for i in range(1, 37)]
    y = [50000.0 * np.sin(2 * np.pi * i / 12) for i in range(1, 37)]
    df = pd.DataFrame({"month": months, "net_inflow_cr": y})
    ets.fit(df)
    assert ets.is_fitted
    preds = ets.forecast(steps=3)
    assert len(preds) == 3
    assert not np.isnan(preds).any()


def test_sarimax_forecaster():
    """Verify SARIMAX with calendar exogenous regressors fits and forecasts."""
    sar = SARIMAXForecaster()
    months = [f"2020-{i:02d}" for i in range(1, 37)]
    y = [50000.0 * np.sin(2 * np.pi * i / 12) for i in range(1, 37)]
    df = pd.DataFrame({
        "month": months,
        "net_inflow_cr": y,
        "is_advance_tax_month": [1 if i % 3 == 0 else 0 for i in range(1, 37)],
        "is_fy_end": [1 if i % 12 == 3 else 0 for i in range(1, 37)],
        "is_post_quarter_month": [1 if i % 3 == 1 else 0 for i in range(1, 37)],
    })
    sar.fit(df)
    assert sar.is_fitted
    future_df = pd.DataFrame({
        "month": ["2023-01", "2023-02", "2023-03"],
        "is_advance_tax_month": [0, 0, 1],
        "is_fy_end": [0, 0, 1],
        "is_post_quarter_month": [1, 0, 0],
    })
    preds = sar.forecast(steps=3, future_df=future_df)
    assert len(preds) == 3
    assert not np.isnan(preds).any()


def test_ridge_direct_forecaster():
    """Verify Direct Ridge multi-step forecaster produces 3 forecasts."""
    ridge = RidgeDirectForecaster()
    # Load sample from processed featured flows
    df = pd.read_csv("data/processed/featured_fund_flows.csv")
    sub = df[df["category"] == "Liquid Fund"].sort_values("month").iloc[:50].reset_index(drop=True)
    ridge.fit(sub)
    assert ridge.is_fitted
    preds = ridge.forecast(steps=3)
    assert len(preds) == 3
    assert not np.isnan(preds).any()


# --- 3. Prediction Intervals Tests ---

def test_intervals_calibrator_leakage_free():
    """Verify prediction interval calibrator only uses past realized OOS errors."""
    calibrator = PredictionIntervalCalibrator()
    
    # Record predictions for origin 2024-01 targeting 2024-02
    calibrator.record_out_of_sample_prediction(
        category="Liquid Fund",
        model_name="ridge",
        origin_month="2024-01",
        target_month="2024-02",
        horizon=1,
        predicted_value=100.0,
    )
    
    # At origin 2024-01, target 2024-02 is NOT realized yet
    errs_at_01 = calibrator.get_available_oos_errors(
        category="Liquid Fund", model_name="ridge", horizon=1, current_origin="2024-01"
    )
    assert len(errs_at_01) == 0  # No leakage!
    
    # Now simulate passing time: actual for 2024-02 is observed
    calibrator.update_actual(target_month="2024-02", category="Liquid Fund", actual_value=120.0)
    
    # At origin 2024-03, error for 2024-02 IS available
    errs_at_03 = calibrator.get_available_oos_errors(
        category="Liquid Fund", model_name="ridge", horizon=1, current_origin="2024-03"
    )
    assert len(errs_at_03) == 1
    assert errs_at_03[0] == 20.0  # (120 - 100)


def test_interval_monotonicity():
    """Verify 95% interval encompasses 80% interval and lower <= upper."""
    calibrator = PredictionIntervalCalibrator()
    df = pd.read_csv("data/processed/featured_fund_flows.csv")
    train_df = df[df["category"] == "Liquid Fund"].iloc[:40].copy()
    
    intervals = calibrator.compute_intervals(
        predicted_value=50000.0,
        category="Liquid Fund",
        model_name="ridge",
        horizon=1,
        origin_month="2024-07",
        train_df=train_df,
    )
    
    assert intervals["lower_80"] <= intervals["upper_80"]
    assert intervals["lower_95"] <= intervals["upper_95"]
    assert intervals["lower_95"] <= intervals["lower_80"]
    assert intervals["upper_95"] >= intervals["upper_80"]


# --- 4. Backtest Boundaries & Data Isolation Tests ---

def test_backtest_origins_count_and_span():
    """Verify exactly 24 origins from July 2024 through June 2026."""
    assert len(EVALUATION_ORIGINS) == 24
    assert EVALUATION_ORIGINS[0] == "2024-07"
    assert EVALUATION_ORIGINS[-1] == "2026-06"


def test_backtest_smoke_run(tmp_path):
    """Smoke test running 2 origins on 2 models to verify pipeline integration."""
    out_csv = str(tmp_path / "test_results.csv")
    summary_csv = str(tmp_path / "test_summary.csv")
    
    results_df, summary_df = run_rolling_origin_backtest(
        origins=["2024-07", "2024-08"],
        models=["seasonal_naive", "ridge"],
        categories=["Liquid Fund"],
        save_results=True,
        output_path=out_csv,
        summary_path=summary_csv,
    )
    
    # 2 origins * 3 horizons * 2 models * 1 category = 12 records
    assert len(results_df) == 12
    assert not summary_df.empty
    assert "mae_cr" in summary_df.columns
    assert "rel_mae" in summary_df.columns


def test_metrics_length_mismatch_validation():
    """Verify that forecasting metrics strictly reject mismatched input vector lengths."""
    y2 = [100.0, 200.0]
    y1 = [100.0]
    y_tr = [50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    with pytest.raises(ValueError, match="Length mismatch"):
        calculate_mae(y2, y1)

    with pytest.raises(ValueError, match="Length mismatch"):
        calculate_rmse(y2, y1)

    with pytest.raises(ValueError, match="Length mismatch"):
        calculate_wape(y2, y1)

    with pytest.raises(ValueError, match="Length mismatch"):
        calculate_mape(y2, y1)

    with pytest.raises(ValueError, match="Length mismatch"):
        calculate_mase(y2, y1, y_train=y_tr)

    with pytest.raises(ValueError, match="Length mismatch"):
        calculate_pinball_loss(y2, y1, alpha=0.1)

    with pytest.raises(ValueError, match="Length mismatch"):
        calculate_interval_coverage(y2, [50.0], [150.0, 250.0])

    with pytest.raises(ValueError, match="Length mismatch"):
        calculate_interval_width([50.0, 60.0], [150.0])


def test_metrics_edge_cases_and_conventions():
    """Verify edge cases: zero denominators, empty vectors, and skill score conventions."""
    # Empty inputs return nan
    assert np.isnan(calculate_mae([], []))
    assert np.isnan(calculate_rmse([], []))
    assert np.isnan(calculate_wape([], []))
    assert np.isnan(calculate_mape([], []))
    assert np.isnan(calculate_mase([], [], [10.0, 20.0]))
    assert np.isnan(calculate_interval_coverage([], [], []))
    assert np.isnan(calculate_interval_width([], []))

    # All actuals zero in WAPE
    assert calculate_wape([0.0, 0.0], [0.0, 0.0]) == 0.0
    assert np.isinf(calculate_wape([0.0, 0.0], [10.0, 20.0]))

    # Skill score direction: positive means model has lower MAE than baseline
    better = calculate_relative_metrics(mae_model=80.0, mae_baseline=100.0)
    assert better["skill_score"] == 0.20
    assert better["rel_mae"] == 0.80

    worse = calculate_relative_metrics(mae_model=120.0, mae_baseline=100.0)
    assert worse["skill_score"] == -0.20
    assert worse["rel_mae"] == 1.20


def test_model_constant_and_extreme_series():
    """Verify forecaster stability when series is completely flat."""
    flat_history = [1000.0] * 36
    df_flat = pd.DataFrame({
        "month": [f"2020-{m:02d}" for m in range(1, 37)],
        "net_inflow_cr": flat_history,
        "is_advance_tax_month": [0] * 36,
        "is_fy_end": [0] * 36,
        "is_post_quarter_month": [0] * 36,
    })

    # Seasonal Naive
    s_naive = SeasonalNaiveForecaster()
    s_naive.fit(df_flat)
    assert np.allclose(s_naive.forecast(steps=3), [1000.0, 1000.0, 1000.0])

    # ETS
    ets = ETSForecaster()
    ets.fit(df_flat)
    ets_preds = ets.forecast(steps=3)
    assert len(ets_preds) == 3
    assert not np.isnan(ets_preds).any()

    # SARIMAX
    sar = SARIMAXForecaster()
    sar.fit(df_flat)
    future_df = pd.DataFrame({
        "month": ["2023-01", "2023-02", "2023-03"],
        "is_advance_tax_month": [0, 0, 0],
        "is_fy_end": [0, 0, 0],
        "is_post_quarter_month": [0, 0, 0],
    })
    sar_preds = sar.forecast(steps=3, future_df=future_df)
    assert len(sar_preds) == 3
    assert not np.isnan(sar_preds).any()


def test_backtest_results_uniqueness_and_integrity():
    """Verify saved backtest records satisfy uniqueness and schema constraints."""
    results_path = "data/processed/backtest_results.csv"
    summary_path = "data/processed/backtest_metrics_summary.csv"

    results_df = pd.read_csv(results_path)
    summary_df = pd.read_csv(summary_path)

    # 576 total backtest records: 24 origins * 3 horizons * 4 models * 2 categories
    assert len(results_df) == 576

    # Compound key uniqueness
    compound_keys = ["origin_month", "target_month", "category", "model_name", "horizon"]
    duplicates = results_df.duplicated(subset=compound_keys)
    assert not duplicates.any(), f"Found {duplicates.sum()} duplicate backtest records!"

    # No nulls in vital forecast columns
    assert results_df["actual_cr"].isnull().sum() == 0
    assert results_df["predicted_cr"].isnull().sum() == 0

    # Summary table verification: 32 rows (24 horizon-specific + 8 pooled rows)
    assert len(summary_df) == 32
    h_rows = summary_df[summary_df["horizon"] != "all"]
    assert (h_rows["eval_count"] == 24).all()
    pooled_rows = summary_df[summary_df["horizon"] == "all"]
    assert (pooled_rows["eval_count"] == 72).all()

