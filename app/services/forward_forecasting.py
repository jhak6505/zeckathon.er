"""
Service module for generating out-of-sample forward projections (next 3 months)
and cash buffer recommendations based on the latest available data origin (2026-09).
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.forecasting.intervals import PredictionIntervalCalibrator
from app.forecasting.models import (
    BaseForecaster,
    ETSForecaster,
    RidgeDirectForecaster,
    SARIMAXForecaster,
    SeasonalNaiveForecaster,
)
from app.services.cash_buffer import (
    BufferRecommendation,
    calculate_cash_buffer_recommendation,
    get_preferred_model,
)

logger = logging.getLogger(__name__)

DEFAULT_FEATURED_PATH = os.path.join("data", "processed", "featured_fund_flows.csv")
DEFAULT_BACKTEST_PATH = os.path.join("data", "processed", "backtest_results.csv")
FORWARD_RESULTS_PATH = os.path.join("data", "processed", "forward_forecasts_3m.csv")


def generate_forward_calendar(start_month: str = "2026-10", steps: int = 3) -> pd.DataFrame:
    """Generate future deterministic calendar features for forward horizons."""
    dates = pd.date_range(start=f"{start_month}-01", periods=steps, freq="MS")
    rows = []
    for dt in dates:
        m_str = dt.strftime("%Y-%m")
        m_num = dt.month
        rows.append({
            "month": m_str,
            "calendar_year": dt.year,
            "calendar_month": m_num,
            "quarter": (m_num - 1) // 3 + 1,
            "days_in_month": dt.days_in_month,
            "is_advance_tax_month": int(m_num in [3, 6, 9, 12]),
            "is_quarter_end": int(m_num in [3, 6, 9, 12]),
            "is_fy_end": int(m_num == 3),
            "is_post_quarter_month": int(m_num in [1, 4, 7, 10]),
            "sin_month": round(np.sin(2 * np.pi * m_num / 12.0), 4),
            "cos_month": round(np.cos(2 * np.pi * m_num / 12.0), 4),
        })
    return pd.DataFrame(rows)


def load_calibrator_from_backtest(backtest_path: str = DEFAULT_BACKTEST_PATH) -> PredictionIntervalCalibrator:
    """Restore PredictionIntervalCalibrator with all verified backtest historical errors."""
    calibrator = PredictionIntervalCalibrator()
    if os.path.exists(backtest_path):
        bkt = pd.read_csv(backtest_path)
        for _, r in bkt.iterrows():
            calibrator.record_out_of_sample_prediction(
                category=r["category"],
                model_name=r["model_name"],
                origin_month=r["origin_month"],
                target_month=r["target_month"],
                horizon=int(r["horizon"]),
                predicted_value=float(r["predicted_cr"]),
            )
            if not pd.isna(r["actual_cr"]):
                calibrator.update_actual(
                    target_month=r["target_month"],
                    category=r["category"],
                    actual_value=float(r["actual_cr"]),
                )
    return calibrator


def generate_3month_forward_forecasts(
    featured_df: Optional[pd.DataFrame] = None,
    save_csv: bool = True,
    output_path: str = FORWARD_RESULTS_PATH,
) -> pd.DataFrame:
    """
    Generate forward forecasts for 2026-10, 2026-11, and 2026-12 across models and categories.
    """
    if featured_df is None:
        if not os.path.exists(DEFAULT_FEATURED_PATH):
            raise FileNotFoundError(f"Featured dataset not found at {DEFAULT_FEATURED_PATH}")
        featured_df = pd.read_csv(DEFAULT_FEATURED_PATH)

    origin_month = "2026-09"
    future_cal = generate_forward_calendar(start_month="2026-10", steps=3)
    target_months = future_cal["month"].tolist()

    calibrator = load_calibrator_from_backtest()
    records: List[Dict[str, Any]] = []

    models_to_run = {
        "seasonal_naive": SeasonalNaiveForecaster,
        "ets": ETSForecaster,
        "sarimax": SARIMAXForecaster,
        "ridge": RidgeDirectForecaster,
    }

    for category in ["Liquid Fund", "Overnight Fund"]:
        cat_df = featured_df[featured_df["category"] == category].sort_values("month").reset_index(drop=True)
        train_df = cat_df[cat_df["month"] <= origin_month].copy()
        current_aum = float(train_df["aum_cr"].iloc[-1])

        for model_name, model_cls in models_to_run.items():
            model_instance = model_cls()
            model_instance.fit(train_df=train_df)
            preds = model_instance.forecast(steps=3, future_df=future_cal)

            for h_idx, target_m in enumerate(target_months):
                h = h_idx + 1
                pred_val = round(float(preds[h_idx]), 2)

                intervals = calibrator.compute_intervals(
                    predicted_value=pred_val,
                    category=category,
                    model_name=model_name,
                    horizon=h,
                    origin_month=origin_month,
                    train_df=train_df,
                )

                records.append({
                    "origin_month": origin_month,
                    "target_month": target_m,
                    "category": category,
                    "model_name": model_name,
                    "horizon": h,
                    "predicted_cr": pred_val,
                    "lower_80": intervals["lower_80"],
                    "upper_80": intervals["upper_80"],
                    "lower_95": intervals["lower_95"],
                    "upper_95": intervals["upper_95"],
                    "q_025": intervals["q_025"],
                    "q_10": intervals["q_10"],
                    "q_90": intervals["q_90"],
                    "q_975": intervals["q_975"],
                    "current_aum_cr": current_aum,
                })

    df_forward = pd.DataFrame(records)
    if save_csv:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_forward.to_csv(output_path, index=False)
        logger.info("Saved 3-month forward forecasts to %s (%d rows)", output_path, len(df_forward))

    return df_forward


def validate_point_forecast_and_interval_compatibility(forward_df: pd.DataFrame) -> None:
    """
    Validate that point forecasts and interval bounds within forward_df are strictly compatible.
    
    Enforces:
    1. Required schema columns exist.
    2. Bounds monotonicity: lower_95 <= lower_80 <= upper_80 <= upper_95.
    3. Prediction inclusion: lower_80 <= predicted_cr <= upper_80 (and 95% bounds).
    4. Categorical and model partitioning integrity (no duplicate category-model-horizon keys).
    """
    required_cols = [
        "category", "model_name", "horizon", "predicted_cr",
        "lower_80", "upper_80", "lower_95", "upper_95",
    ]
    for col in required_cols:
        if col not in forward_df.columns:
            raise ValueError(f"Missing required forward forecast column: {col}")

    # Check for duplicate keys
    dups = forward_df.duplicated(subset=["category", "model_name", "horizon"])
    if dups.any():
        raise ValueError("Duplicate (category, model_name, horizon) entries detected in forward DataFrame.")

    for idx, row in forward_df.iterrows():
        cat = row["category"]
        model = row["model_name"]
        h = row["horizon"]
        pred = float(row["predicted_cr"])
        l80 = float(row["lower_80"])
        u80 = float(row["upper_80"])
        l95 = float(row["lower_95"])
        u95 = float(row["upper_95"])

        if not (l95 <= l80 <= u80 <= u95):
            raise ValueError(
                f"Interval bounds ordering violation for {cat} / {model} / h={h}: "
                f"l95={l95}, l80={l80}, u80={u80}, u95={u95}"
            )
        if not (l80 <= pred <= u80) or not (l95 <= pred <= u95):
            raise ValueError(
                f"Point forecast {pred} falls outside calibrated bounds [{l80}, {u80}] "
                f"for {cat} / {model} / h={h}. Model forecast and error quantiles must not be mixed."
            )


def get_forward_recommendation(
    category: str,
    horizon_months: int,
    risk_tolerance: str = "moderate",
    base_buffer_pct: Optional[float] = None,
    forward_df: Optional[pd.DataFrame] = None,
    step_wise_preferred: bool = False,
) -> BufferRecommendation:
    """
    Generate cash buffer recommendation for the upcoming planning horizon (from origin 2026-09).
    
    Model Selection Strategies:
    - step_wise_preferred=False (Production Default): Evaluates a single dynamically coherent model
      family based on get_preferred_model(category, horizon_months).
      Liquid Funds: SARIMAX across all horizons (h=1, 2, 3).
      Overnight Funds: SARIMAX at h=1; Seasonal-Naive for multi-month horizon (h=2, 3).
    - step_wise_preferred=True: Stitches step-wise champion models per horizon step
      (e.g., Overnight Fund: SARIMAX at h=1, Seasonal-Naive at h=2, Seasonal-Naive at h=3),
      strictly ensuring point forecasts and error quantiles match within each step.
    """
    if forward_df is None:
        if os.path.exists(FORWARD_RESULTS_PATH):
            forward_df = pd.read_csv(FORWARD_RESULTS_PATH)
        else:
            forward_df = generate_3month_forward_forecasts()

    # Verify input compatibility
    validate_point_forecast_and_interval_compatibility(forward_df)

    risk_tol = risk_tolerance.lower().strip()
    is_conservative = risk_tol in ["conservative", "95", "95%"]

    if not step_wise_preferred:
        preferred_model = get_preferred_model(category, horizon_months)
        sub = forward_df[
            (forward_df["category"] == category) &
            (forward_df["model_name"] == preferred_model)
        ].sort_values("horizon").reset_index(drop=True)

        if len(sub) < horizon_months:
            raise ValueError(f"Insufficient forward rows for {category} ({len(sub)} < {horizon_months})")

        # Strict validation: Ensure point forecasts and intervals belong strictly to preferred_model
        if not (sub["model_name"].iloc[:horizon_months] == preferred_model).all():
            raise ValueError(f"Model mismatch detected in forward slice: expected {preferred_model}")

        forecast_flows = sub["predicted_cr"].iloc[:horizon_months].tolist()
        lower_bounds = (
            sub["lower_95"].iloc[:horizon_months].tolist()
            if is_conservative
            else sub["lower_80"].iloc[:horizon_months].tolist()
        )
        upper_bounds = (
            sub["upper_95"].iloc[:horizon_months].tolist()
            if is_conservative
            else sub["upper_80"].iloc[:horizon_months].tolist()
        )
        current_aum = float(sub["current_aum_cr"].iloc[0])
        model_name_used = preferred_model
    else:
        forecast_flows = []
        lower_bounds = []
        upper_bounds = []
        model_names_used = []
        current_aum = None

        for h in range(1, horizon_months + 1):
            h_model = get_preferred_model(category, h)
            model_names_used.append(h_model)
            h_row = forward_df[
                (forward_df["category"] == category) &
                (forward_df["model_name"] == h_model) &
                (forward_df["horizon"] == h)
            ]
            if len(h_row) != 1:
                raise ValueError(
                    f"Expected exactly 1 row for {category}, model {h_model}, horizon {h}; got {len(h_row)}"
                )

            row = h_row.iloc[0]
            if row["model_name"] != h_model:
                raise ValueError(f"Model mismatch at horizon {h}: expected {h_model}, got {row['model_name']}")

            forecast_flows.append(float(row["predicted_cr"]))
            lower_bounds.append(float(row["lower_95"] if is_conservative else row["lower_80"]))
            upper_bounds.append(float(row["upper_95"] if is_conservative else row["upper_80"]))
            if current_aum is None:
                current_aum = float(row["current_aum_cr"])

        model_name_used = "+".join(model_names_used)

    return calculate_cash_buffer_recommendation(
        category=category,
        horizon_months=horizon_months,
        forecast_flows=forecast_flows,
        lower_bounds=lower_bounds,
        upper_bounds=upper_bounds,
        current_aum=current_aum,
        risk_tolerance=risk_tolerance,
        base_buffer_pct=base_buffer_pct,
        model_name=model_name_used,
    )

