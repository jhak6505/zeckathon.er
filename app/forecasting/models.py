"""
Forecasting models module for FINHYPE.

Implements:
1. SeasonalNaiveForecaster (Benchmark persistence baseline)
2. ETSForecaster (Holt-Winters Additive Exponential Smoothing)
3. SARIMAXForecaster (Seasonal ARIMA with calendar & lagged macro regressors)
4. RidgeDirectForecaster (Direct Multi-Step L2-regularized linear model)
5. LightGBMDirectForecaster (Optional / Secondary constrained tree model)
"""

from __future__ import annotations

import logging
import warnings
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

logger = logging.getLogger(__name__)


class BaseForecaster(ABC):
    """Abstract base class for all FINHYPE forecasting estimators."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.is_fitted = False
        self.diagnostics: Dict[str, Any] = {
            "status": "unfitted",
            "fallback_used": False,
            "fallback_reason": None,
            "warnings": [],
        }

    @abstractmethod
    def fit(self, train_df: pd.DataFrame) -> "BaseForecaster":
        """Fit model on training dataframe up to forecast origin T."""
        pass

    @abstractmethod
    def forecast(
        self,
        steps: int = 3,
        future_df: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        """Generate multi-step point forecasts for horizons 1..steps."""
        pass


class SeasonalNaiveForecaster(BaseForecaster):
    """
    Seasonal-Naive Baseline Forecaster.
    
    Persists the value observed exactly 12 months prior:
    hat{Y}_{T+h} = Y_{T+h-12}
    If 12-month lag is unavailable (very early samples), falls back to last observed value.
    """

    def __init__(self) -> None:
        super().__init__(name="seasonal_naive")
        self.history: np.ndarray = np.array([])
        self.seasonal_period = 12

    def fit(self, train_df: pd.DataFrame) -> "SeasonalNaiveForecaster":
        train_sorted = train_df.sort_values("month").reset_index(drop=True)
        self.history = train_sorted["net_inflow_cr"].to_numpy(dtype=float)
        self.is_fitted = True
        self.diagnostics["status"] = "fitted"
        return self

    def forecast(
        self,
        steps: int = 3,
        future_df: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError(f"{self.name} must be fitted before forecasting.")
            
        n = len(self.history)
        preds = []
        for h in range(1, steps + 1):
            lag_idx = n + h - 1 - self.seasonal_period
            if lag_idx >= 0:
                preds.append(float(self.history[lag_idx]))
            else:
                # Fall back to latest available historical value if less than 12 months of history
                preds.append(float(self.history[-1]))
        return np.array(preds, dtype=float)


class ETSForecaster(BaseForecaster):
    """
    Exponential Smoothing (ETS) Forecaster.
    
    Uses Holt-Winters Additive Error, Additive Damped Trend, and Additive Seasonality:
    ETS(A, Ad, A) with seasonal period m=12.
    Strictly additive to accommodate zero and negative net flow values.
    """

    def __init__(self, seasonal_periods: int = 12, damped_trend: bool = True) -> None:
        super().__init__(name="ets")
        self.seasonal_periods = seasonal_periods
        self.damped_trend = damped_trend
        self.fitted_model: Optional[Any] = None
        self.history: np.ndarray = np.array([])

    def fit(self, train_df: pd.DataFrame) -> "ETSForecaster":
        train_sorted = train_df.sort_values("month").reset_index(drop=True)
        y = train_sorted["net_inflow_cr"].to_numpy(dtype=float)
        self.history = y
        
        # Need at least 2 full seasonal cycles (24 months) for stable seasonal Holt-Winters
        if len(y) < 2 * self.seasonal_periods:
            self.diagnostics["fallback_used"] = True
            self.diagnostics["fallback_reason"] = f"Insufficient history ({len(y)} < 24) for seasonal ETS; fallback to S-Naive."
            self.is_fitted = True
            self.diagnostics["status"] = "fitted_with_fallback"
            return self

        try:
            with warnings.catch_warnings(record=True) as caught_warnings:
                warnings.simplefilter("always")
                model = ExponentialSmoothing(
                    y,
                    seasonal_periods=self.seasonal_periods,
                    trend="add",
                    seasonal="add",
                    damped_trend=self.damped_trend,
                    initialization_method="estimated",
                )
                self.fitted_model = model.fit(optimized=True)
                for w in caught_warnings:
                    self.diagnostics["warnings"].append(str(w.message))
            self.diagnostics["status"] = "fitted"
            self.is_fitted = True
        except Exception as e:
            logger.warning("ETS fitting failed: %s. Using seasonal naive fallback.", e)
            self.diagnostics["fallback_used"] = True
            self.diagnostics["fallback_reason"] = f"Fitting exception: {e}"
            self.diagnostics["status"] = "fitted_with_fallback"
            self.is_fitted = True
            
        return self

    def forecast(
        self,
        steps: int = 3,
        future_df: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError(f"{self.name} must be fitted before forecasting.")
            
        if self.diagnostics["fallback_used"] or self.fitted_model is None:
            # Fallback to seasonal naive persistence
            s_naive = SeasonalNaiveForecaster()
            s_naive.history = self.history
            s_naive.is_fitted = True
            return s_naive.forecast(steps=steps)
            
        try:
            preds = self.fitted_model.forecast(steps=steps)
            return np.asarray(preds, dtype=float)
        except Exception as e:
            logger.warning("ETS forecast generation failed: %s; falling back.", e)
            s_naive = SeasonalNaiveForecaster()
            s_naive.history = self.history
            s_naive.is_fitted = True
            return s_naive.forecast(steps=steps)


class SARIMAXForecaster(BaseForecaster):
    """
    Seasonal ARIMA with Exogenous Regressors (SARIMAX).
    
    Regressors include deterministic calendar flags (advance tax, FY end, post-quarter).
    Macroeconomic regressors are strictly lagged to origin T with zero future change assumption:
    Repo_{T+h} = Repo_T ==> Delta Repo = 0.
    """

    def __init__(
        self,
        order: Tuple[int, int, int] = (1, 0, 0),
        seasonal_order: Tuple[int, int, int, int] = (1, 0, 0, 12),
        exog_cols: Optional[List[str]] = None,
    ) -> None:
        super().__init__(name="sarimax")
        self.order = order
        self.seasonal_order = seasonal_order
        if exog_cols is None:
            exog_cols = ["is_advance_tax_month", "is_fy_end", "is_post_quarter_month"]
        self.exog_cols = exog_cols
        self.fitted_model: Optional[Any] = None
        self.history: np.ndarray = np.array([])

    def fit(self, train_df: pd.DataFrame) -> "SARIMAXForecaster":
        train_sorted = train_df.sort_values("month").reset_index(drop=True)
        y = train_sorted["net_inflow_cr"].to_numpy(dtype=float)
        self.history = y
        
        # Verify exog columns are present
        missing_exog = [c for c in self.exog_cols if c not in train_sorted.columns]
        exog = None if missing_exog else train_sorted[self.exog_cols].to_numpy(dtype=float)
        
        try:
            with warnings.catch_warnings(record=True) as caught_warnings:
                warnings.simplefilter("always")
                model = SARIMAX(
                    y,
                    exog=exog,
                    order=self.order,
                    seasonal_order=self.seasonal_order,
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                self.fitted_model = model.fit(disp=False, maxiter=200)
                for w in caught_warnings:
                    self.diagnostics["warnings"].append(str(w.message))
            self.diagnostics["status"] = "fitted"
            self.is_fitted = True
        except Exception as e:
            logger.warning("SARIMAX fitting failed: %s; recording fallback.", e)
            self.diagnostics["fallback_used"] = True
            self.diagnostics["fallback_reason"] = f"Fitting exception: {e}"
            self.diagnostics["status"] = "fitted_with_fallback"
            self.is_fitted = True
            
        return self

    def forecast(
        self,
        steps: int = 3,
        future_df: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError(f"{self.name} must be fitted before forecasting.")
            
        if self.diagnostics["fallback_used"] or self.fitted_model is None:
            # S-Naive fallback
            s_naive = SeasonalNaiveForecaster()
            s_naive.history = self.history
            s_naive.is_fitted = True
            return s_naive.forecast(steps=steps)
            
        exog_future = None
        if future_df is not None and all(c in future_df.columns for c in self.exog_cols):
            exog_future = future_df[self.exog_cols].iloc[:steps].to_numpy(dtype=float)
            
        try:
            preds = self.fitted_model.forecast(steps=steps, exog=exog_future)
            return np.asarray(preds, dtype=float)
        except Exception as e:
            logger.warning("SARIMAX forecast failed: %s; falling back.", e)
            s_naive = SeasonalNaiveForecaster()
            s_naive.history = self.history
            s_naive.is_fitted = True
            return s_naive.forecast(steps=steps)


class RidgeDirectForecaster(BaseForecaster):
    """
    Direct Multi-Step Ridge Regression Forecaster (Primary Regularized ML Model).
    
    Trains separate L2-regularized linear models for horizons h in {1, 2, 3}.
    Target for model h is Y_{t+h}.
    Features are strictly those available at forecast origin t.
    """

    def __init__(
        self,
        alphas: Optional[Sequence[float]] = None,
        feature_cols: Optional[List[str]] = None,
    ) -> None:
        super().__init__(name="ridge")
        if alphas is None:
            alphas = (0.1, 1.0, 10.0, 50.0, 100.0, 500.0, 1000.0)
        self.alphas = alphas
        
        if feature_cols is None:
            feature_cols = [
                "is_advance_tax_month", "is_fy_end", "is_post_quarter_month",
                "sin_month", "cos_month", "days_in_month",
                "net_inflow_lag_1", "net_inflow_lag_2", "net_inflow_lag_12",
                "net_inflow_roll_mean_3", "net_inflow_roll_std_3",
                "churn_ratio_lag_1", "flow_to_aum_pct_lag_1",
                "peer_net_inflow_lag_1", "repo_rate_lag_1", "nifty_return_pct_lag_1"
            ]
        self.feature_cols = feature_cols
        self.models: Dict[int, RidgeCV] = {}
        self.scalers: Dict[int, StandardScaler] = {}
        self.history: np.ndarray = np.array([])
        self.last_features_row: Optional[pd.Series] = None

    def fit(self, train_df: pd.DataFrame) -> "RidgeDirectForecaster":
        train_sorted = train_df.sort_values("month").reset_index(drop=True)
        self.history = train_sorted["net_inflow_cr"].to_numpy(dtype=float)
        
        # Filter available feature columns
        active_cols = [c for c in self.feature_cols if c in train_sorted.columns]
        if not active_cols:
            self.diagnostics["fallback_used"] = True
            self.diagnostics["fallback_reason"] = "No valid feature columns found for Ridge."
            self.is_fitted = True
            return self
            
        self.last_features_row = train_sorted[active_cols].iloc[-1]
        
        # Build direct training pairs for horizons h in {1, 2, 3}
        for h in [1, 2, 3]:
            # Feature matrix at time t, Target at time t+h
            # Sample t runs from 0 up to len(train_sorted) - h - 1
            N = len(train_sorted)
            if N <= h + 12:  # Need minimum training samples
                continue
                
            X_rows = []
            y_rows = []
            
            for t_idx in range(12, N - h):
                row_t = train_sorted[active_cols].iloc[t_idx]
                target_val = train_sorted["net_inflow_cr"].iloc[t_idx + h]
                
                # Check for NaNs
                if row_t.isna().any() or np.isnan(target_val):
                    continue
                    
                X_rows.append(row_t.to_numpy(dtype=float))
                y_rows.append(float(target_val))
                
            if len(X_rows) >= 10:
                X_arr = np.array(X_rows)
                y_arr = np.array(y_rows)
                
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X_arr)
                
                ridge = RidgeCV(alphas=self.alphas)
                ridge.fit(X_scaled, y_arr)
                
                self.scalers[h] = scaler
                self.models[h] = ridge
                
        if len(self.models) == 3:
            self.diagnostics["status"] = "fitted"
            self.is_fitted = True
        else:
            self.diagnostics["fallback_used"] = True
            self.diagnostics["fallback_reason"] = f"Insufficient direct pairs (fitted {len(self.models)}/3 horizons)."
            self.diagnostics["status"] = "partially_fitted"
            self.is_fitted = True
            
        return self

    def forecast(
        self,
        steps: int = 3,
        future_df: Optional[pd.DataFrame] = None,
    ) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError(f"{self.name} must be fitted before forecasting.")
            
        preds = []
        for h in range(1, steps + 1):
            if h in self.models and self.last_features_row is not None:
                row_vec = self.last_features_row.to_numpy(dtype=float).reshape(1, -1)
                
                # If future_df is provided with deterministic calendar features for target month t+h,
                # update the calendar columns for the target horizon
                if future_df is not None and len(future_df) >= h:
                    target_cal = future_df.iloc[h - 1]
                    active_cols = [c for c in self.feature_cols if c in future_df.columns]
                    updated_row = self.last_features_row.copy()
                    for cal_c in ["is_advance_tax_month", "is_fy_end", "is_post_quarter_month", "sin_month", "cos_month", "days_in_month"]:
                        if cal_c in target_cal and cal_c in updated_row:
                            updated_row[cal_c] = target_cal[cal_c]
                    row_vec = updated_row.to_numpy(dtype=float).reshape(1, -1)
                    
                X_scaled = self.scalers[h].transform(row_vec)
                pred_val = float(self.models[h].predict(X_scaled)[0])
                preds.append(pred_val)
            else:
                # Fallback to seasonal naive for this horizon
                s_naive = SeasonalNaiveForecaster()
                s_naive.history = self.history
                s_naive.is_fitted = True
                s_preds = s_naive.forecast(steps=steps)
                preds.append(float(s_preds[h - 1]))
                
        return np.array(preds, dtype=float)


def get_available_models() -> Dict[str, BaseForecaster]:
    """
    Return dictionary of core forecasters.
    
    1. seasonal_naive (benchmark)
    2. ets (exponential smoothing)
    3. sarimax (econometric)
    4. ridge (regularized direct ML)
    """
    return {
        "seasonal_naive": SeasonalNaiveForecaster(),
        "ets": ETSForecaster(),
        "sarimax": SARIMAXForecaster(),
        "ridge": RidgeDirectForecaster(),
    }

