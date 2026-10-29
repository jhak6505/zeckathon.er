"""
Rolling-origin backtesting engine for FINHYPE.

Executes expanding-window backtest over 24 forecast origins (July 2024 through June 2026).
Ensures zero data leakage across feature generation, scaling, model fitting, and interval calibration.
Evaluates Liquid and Overnight Funds separately for horizons 1, 2, and 3.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.forecasting.intervals import PredictionIntervalCalibrator
from app.forecasting.metrics import (
    calculate_epsilon_floor,
    calculate_mae,
    calculate_relative_metrics,
    compute_all_metrics,
)
from app.forecasting.models import (
    BaseForecaster,
    ETSForecaster,
    RidgeDirectForecaster,
    SARIMAXForecaster,
    SeasonalNaiveForecaster,
)

logger = logging.getLogger(__name__)

DEFAULT_FEATURED_PATH = os.path.join("data", "processed", "featured_fund_flows.csv")
DEFAULT_RESULTS_PATH = os.path.join("data", "processed", "backtest_results.csv")
DEFAULT_SUMMARY_PATH = os.path.join("data", "processed", "backtest_metrics_summary.csv")

# The 24 evaluation origins: July 2024 through June 2026
EVALUATION_ORIGINS: List[str] = [
    "2024-07", "2024-08", "2024-09", "2024-10", "2024-11", "2024-12",
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
]


def instantiate_model(model_name: str) -> BaseForecaster:
    """Instantiate a fresh estimator instance by name."""
    if model_name == "seasonal_naive":
        return SeasonalNaiveForecaster()
    elif model_name == "ets":
        return ETSForecaster()
    elif model_name == "sarimax":
        return SARIMAXForecaster()
    elif model_name == "ridge":
        return RidgeDirectForecaster()
    elif model_name == "lightgbm":
        try:
            import lightgbm as lgb
            # We will use Ridge or fallback if lightgbm is missing
            raise NotImplementedError("LightGBM optional package not installed in environment.")
        except ImportError:
            raise ImportError("LightGBM is not installed.")
    else:
        raise ValueError(f"Unknown model name: {model_name}")


def run_rolling_origin_backtest(
    featured_df: Optional[pd.DataFrame] = None,
    origins: Optional[List[str]] = None,
    models: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    save_results: bool = True,
    output_path: str = DEFAULT_RESULTS_PATH,
    summary_path: str = DEFAULT_SUMMARY_PATH,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Execute 24-origin expanding window backtesting across models, categories, and horizons.
    
    Returns:
    - results_df: 576 rows (24 origins * 3 horizons * 4 models * 2 categories) with actuals, predictions, intervals.
    - summary_df: Aggregated performance metrics by category, model, and horizon.
    """
    if featured_df is None:
        if not os.path.exists(DEFAULT_FEATURED_PATH):
            raise FileNotFoundError(f"Featured dataset not found at {DEFAULT_FEATURED_PATH}")
        featured_df = pd.read_csv(DEFAULT_FEATURED_PATH)
        
    if origins is None:
        origins = EVALUATION_ORIGINS
    if models is None:
        models = ["seasonal_naive", "ets", "sarimax", "ridge"]
    if categories is None:
        categories = ["Liquid Fund", "Overnight Fund"]
        
    logger.info(
        "Starting rolling-origin backtest: %d origins, %d models, %d categories, 3 horizons.",
        len(origins), len(models), len(categories)
    )
    
    calibrator = PredictionIntervalCalibrator()
    records: List[Dict[str, Any]] = []
    
    # Sort data chronologically
    df_all = featured_df.sort_values(by=["category", "month"]).reset_index(drop=True)
    all_months = sorted(df_all["month"].unique().tolist())
    
    for origin in origins:
        origin_idx = all_months.index(origin)
        # 3 future target months
        target_months = all_months[origin_idx + 1 : origin_idx + 4]
        if len(target_months) < 3:
            logger.warning("Origin %s has fewer than 3 future months available; skipping.", origin)
            continue
            
        for category in categories:
            cat_df = df_all[df_all["category"] == category].sort_values("month").reset_index(drop=True)
            
            # 1. STRICT DATA ISOLATION: Training data strictly <= origin
            train_df = cat_df[cat_df["month"] <= origin].copy()
            y_train = train_df["net_inflow_cr"].to_numpy(dtype=float)
            
            # Origin-specific MAPE floor (strictly from y_train)
            eps_floor = calculate_epsilon_floor(y_train)
            
            # Target future frame with deterministic calendar variables
            future_df = cat_df[cat_df["month"].isin(target_months)].copy()
            actuals_dict = future_df.set_index("month")["net_inflow_cr"].to_dict()
            
            # Before forecasting, update calibrator with any newly realized actuals up to this origin
            for past_m in train_df["month"].unique():
                val = train_df[train_df["month"] == past_m]["net_inflow_cr"].iloc[0]
                calibrator.update_actual(target_month=past_m, category=category, actual_value=val)
                
            for model_name in models:
                # Instantiate fresh model
                model = instantiate_model(model_name)
                
                # Fit model strictly on train_df
                model.fit(train_df=train_df)
                
                # Forecast 3 steps ahead
                preds = model.forecast(steps=3, future_df=future_df)
                
                # Extract diagnostics
                fallback_used = model.diagnostics.get("fallback_used", False)
                fallback_reason = model.diagnostics.get("fallback_reason", None)
                
                for h_idx, target_m in enumerate(target_months):
                    horizon = h_idx + 1
                    pred_val = round(float(preds[h_idx]), 2)
                    actual_val = round(float(actuals_dict[target_m]), 2) if target_m in actuals_dict else np.nan
                    
                    # Record forecast into calibrator error archive
                    calibrator.record_out_of_sample_prediction(
                        category=category,
                        model_name=model_name,
                        origin_month=origin,
                        target_month=target_m,
                        horizon=horizon,
                        predicted_value=pred_val,
                    )
                    
                    # Compute prediction intervals strictly using past OOS errors
                    intervals = calibrator.compute_intervals(
                        predicted_value=pred_val,
                        category=category,
                        model_name=model_name,
                        horizon=horizon,
                        origin_month=origin,
                        train_df=train_df,
                    )
                    
                    record = {
                        "origin_month": origin,
                        "target_month": target_m,
                        "category": category,
                        "model_name": model_name,
                        "horizon": horizon,
                        "actual_cr": actual_val,
                        "predicted_cr": pred_val,
                        "lower_80": intervals["lower_80"],
                        "upper_80": intervals["upper_80"],
                        "lower_95": intervals["lower_95"],
                        "upper_95": intervals["upper_95"],
                        "q_025": intervals["q_025"],
                        "q_10": intervals["q_10"],
                        "q_90": intervals["q_90"],
                        "q_975": intervals["q_975"],
                        "epsilon_floor_cr": eps_floor,
                        "fallback_used": int(fallback_used),
                        "fallback_reason": fallback_reason or "none",
                    }
                    records.append(record)
                    
    results_df = pd.DataFrame(records)
    logger.info("Generated %d backtest forecast rows.", len(results_df))
    
    # Compute Summary Performance Metrics
    summary_df = generate_backtest_summary(results_df, df_all)
    
    if save_results:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        results_df.to_csv(output_path, index=False)
        summary_df.to_csv(summary_path, index=False)
        logger.info("Saved backtest detailed results to %s", output_path)
        logger.info("Saved backtest metrics summary to %s", summary_path)
        
    return results_df, summary_df


def generate_backtest_summary(
    results_df: pd.DataFrame,
    full_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggregate evaluation metrics across origins by category, model, and horizon.
    Includes relative MAE and Skill Score compared to Seasonal-Naive.
    """
    summary_rows: List[Dict[str, Any]] = []
    
    categories = results_df["category"].unique()
    models = results_df["model_name"].unique()
    
    for category in categories:
        cat_full = full_df[full_df["category"] == category].sort_values("month")
        y_train_full = cat_full["net_inflow_cr"].to_numpy(dtype=float)
        cat_results = results_df[results_df["category"] == category]
        
        # 1. First compute Seasonal-Naive baseline MAEs for each horizon to anchor relative comparisons
        s_naive_sub = cat_results[cat_results["model_name"] == "seasonal_naive"]
        baseline_maes: Dict[Any, float] = {}
        for h in [1, 2, 3]:
            h_sub = s_naive_sub[s_naive_sub["horizon"] == h]
            baseline_maes[h] = calculate_mae(h_sub["actual_cr"], h_sub["predicted_cr"])
        baseline_maes["overall"] = calculate_mae(s_naive_sub["actual_cr"], s_naive_sub["predicted_cr"])
        
        for model in models:
            model_sub = cat_results[cat_results["model_name"] == model]
            
            # Evaluate each horizon 1, 2, 3 separately
            for h in [1, 2, 3]:
                h_sub = model_sub[model_sub["horizon"] == h]
                metrics = compute_all_metrics(
                    y_true=h_sub["actual_cr"],
                    y_pred=h_sub["predicted_cr"],
                    y_train=y_train_full,
                    lower_80=h_sub["lower_80"],
                    upper_80=h_sub["upper_80"],
                    lower_95=h_sub["lower_95"],
                    upper_95=h_sub["upper_95"],
                    q_10=h_sub["q_10"],
                    q_90=h_sub["q_90"],
                    q_025=h_sub["q_025"],
                    q_975=h_sub["q_975"],
                    baseline_mae=baseline_maes[h],
                )
                
                row = {
                    "category": category,
                    "model_name": model,
                    "horizon": str(h),
                    "eval_count": len(h_sub),
                    "fallbacks_count": int(h_sub["fallback_used"].sum()),
                    **metrics,
                }
                summary_rows.append(row)
                
            # Evaluate overall pooled horizon (h=1..3)
            metrics_overall = compute_all_metrics(
                y_true=model_sub["actual_cr"],
                y_pred=model_sub["predicted_cr"],
                y_train=y_train_full,
                lower_80=model_sub["lower_80"],
                upper_80=model_sub["upper_80"],
                lower_95=model_sub["lower_95"],
                upper_95=model_sub["upper_95"],
                q_10=model_sub["q_10"],
                q_90=model_sub["q_90"],
                q_025=model_sub["q_025"],
                q_975=model_sub["q_975"],
                baseline_mae=baseline_maes["overall"],
            )
            row_overall = {
                "category": category,
                "model_name": model,
                "horizon": "all",
                "eval_count": len(model_sub),
                "fallbacks_count": int(model_sub["fallback_used"].sum()),
                **metrics_overall,
            }
            summary_rows.append(row_overall)
            
    return pd.DataFrame(summary_rows)

