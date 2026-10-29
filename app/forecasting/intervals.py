"""
Prediction intervals module for FINHYPE.

Constructs horizon-specific 80% and 95% prediction intervals and pinball quantiles
using strictly out-of-sample historical forecast errors available at each forecast origin.

STRICT DESIGN SAFEGUARDS:
1. In-sample training residuals are strictly prohibited for interval calibration.
2. Prediction intervals are horizon-specific (expanding for h=1, h=2, h=3).
3. Calibration information at origin T strictly uses errors from past origins where actuals have been observed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PredictionIntervalCalibrator:
    """
    Horizon-specific prediction interval engine based on expanding out-of-sample errors.
    
    Maintains an archive of historical out-of-sample forecast errors:
    e_{tau, h} = Y_{tau+h} - hat{Y}_{tau+h|tau}
    where tau + h <= T (i.e. ground truth has been realized).
    """

    def __init__(self) -> None:
        # Key: (category, model_name, horizon) -> List of Dict with origin_month, error
        self.error_archive: Dict[Tuple[str, str, int], List[Dict[str, Any]]] = {}

    def record_out_of_sample_prediction(
        self,
        category: str,
        model_name: str,
        origin_month: str,
        target_month: str,
        horizon: int,
        predicted_value: float,
    ) -> None:
        """Register an out-of-sample forecast generated at origin_month for target_month."""
        key = (category, model_name, horizon)
        if key not in self.error_archive:
            self.error_archive[key] = []
        self.error_archive[key].append({
            "origin_month": origin_month,
            "target_month": target_month,
            "horizon": horizon,
            "pred": float(predicted_value),
            "actual": None,
            "error": None,  # Will be populated when actual is observed
        })

    def update_actual(self, target_month: str, category: str, actual_value: float) -> None:
        """Update actual ground truth for past forecasts once observed."""
        for (cat, model_name, h), records in self.error_archive.items():
            if cat == category:
                for rec in records:
                    if rec["target_month"] == target_month and rec["actual"] is None:
                        rec["actual"] = float(actual_value)
                        # Error defined as (Actual - Forecast)
                        rec["error"] = float(actual_value - rec["pred"])

    def get_available_oos_errors(
        self,
        category: str,
        model_name: str,
        horizon: int,
        current_origin: str,
    ) -> np.ndarray:
        """
        Retrieve genuine out-of-sample errors strictly realized prior to current_origin.
        
        Only forecasts whose target_month <= current_origin are available to the forecaster.
        """
        key = (category, model_name, horizon)
        if key not in self.error_archive:
            return np.array([], dtype=float)
            
        realized_errors = [
            r["error"]
            for r in self.error_archive[key]
            if r["error"] is not None and r["target_month"] <= current_origin
        ]
        return np.array(realized_errors, dtype=float)

    def generate_initial_cross_validation_errors(
        self,
        train_df: pd.DataFrame,
        category: str,
        model_name: str,
        horizon: int,
        n_splits: int = 5,
    ) -> np.ndarray:
        """
        Generate pseudo out-of-sample errors via temporal expanding cross-validation on train_df.
        
        Used only during early origins before sufficient live backtest errors accumulate.
        Never uses in-sample residuals: splits train_df into temporal folds and trains on past to predict future.
        """
        sub = train_df[train_df["category"] == category].sort_values("month").reset_index(drop=True)
        y = sub["net_inflow_cr"].to_numpy(dtype=float)
        N = len(y)
        
        if N < 24:
            # If historical data is very short, use seasonal difference residuals as fallback scale
            if N > 12:
                diffs = y[12:] - y[:-12]
            else:
                diffs = y[1:] - y[:-1]
            return diffs
            
        cv_errors = []
        # Create rolling temporal splits
        min_train = max(24, N - (n_splits * 2))
        step_size = max(1, (N - min_train - horizon) // n_splits) if n_splits > 0 else 1
        
        for split_end in range(min_train, N - horizon + 1, step_size):
            y_fold_train = y[:split_end]
            y_fold_actual = y[split_end + horizon - 1]
            
            # Use seasonal naive persistence on fold as robust reference predictor
            if len(y_fold_train) >= 12:
                pred = y_fold_train[-12 + horizon - 1] if (-12 + horizon - 1) < 0 else y_fold_train[-1]
            else:
                pred = y_fold_train[-1]
                
            err = y_fold_actual - pred
            cv_errors.append(err)
            
        return np.array(cv_errors, dtype=float)

    def compute_intervals(
        self,
        predicted_value: float,
        category: str,
        model_name: str,
        horizon: int,
        origin_month: str,
        train_df: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Compute horizon-specific 80% and 95% prediction intervals and pinball quantiles.
        
        Bounds:
        lower_80 = pred + Quantile_{0.10}(errors)
        upper_80 = pred + Quantile_{0.90}(errors)
        lower_95 = pred + Quantile_{0.025}(errors)
        upper_95 = pred + Quantile_{0.975}(errors)
        """
        # 1. Check for genuine realized live OOS errors up to origin_month
        oos_errors = self.get_available_oos_errors(category, model_name, horizon, origin_month)
        
        # 2. If fewer than 8 live errors, supplement with expanding cross-validation errors from train_df
        if len(oos_errors) < 8:
            cv_errs = self.generate_initial_cross_validation_errors(
                train_df=train_df,
                category=category,
                model_name=model_name,
                horizon=horizon,
            )
            combined_errors = (
                np.concatenate([oos_errors, cv_errs]) if len(oos_errors) > 0 else cv_errs
            )
        else:
            combined_errors = oos_errors
            
        if len(combined_errors) == 0:
            # Fallback scale based on standard deviation of training net flows
            std_y = float(train_df["net_inflow_cr"].std())
            mult = np.sqrt(horizon)
            q025_err = -1.96 * std_y * mult
            q10_err = -1.282 * std_y * mult
            q90_err = 1.282 * std_y * mult
            q975_err = 1.96 * std_y * mult
        else:
            # Expanding horizon multiplier for multi-step uncertainty
            # If errors came from CV, apply standard multi-step error expansion factor
            h_scale = np.sqrt(horizon)
            scaled_errors = combined_errors * (1.0 if len(oos_errors) >= 8 else h_scale)
            
            q025_err = float(np.percentile(scaled_errors, 2.5))
            q10_err = float(np.percentile(scaled_errors, 10.0))
            q90_err = float(np.percentile(scaled_errors, 90.0))
            q975_err = float(np.percentile(scaled_errors, 97.5))
            
        lower_80 = round(float(predicted_value + q10_err), 2)
        upper_80 = round(float(predicted_value + q90_err), 2)
        lower_95 = round(float(predicted_value + q025_err), 2)
        upper_95 = round(float(predicted_value + q975_err), 2)
        
        # Ensure monotonic ordering (lower <= upper)
        if lower_80 > upper_80:
            lower_80, upper_80 = upper_80, lower_80
        if lower_95 > upper_95:
            lower_95, upper_95 = upper_95, lower_95
            
        # Ensure 95% interval encompasses 80% interval
        lower_95 = min(lower_95, lower_80)
        upper_95 = max(upper_95, upper_80)
        
        return {
            "lower_80": lower_80,
            "upper_80": upper_80,
            "lower_95": lower_95,
            "upper_95": upper_95,
            "q_025": lower_95,
            "q_10": lower_80,
            "q_90": upper_80,
            "q_975": upper_95,
            "error_sample_size": len(combined_errors),
        }

