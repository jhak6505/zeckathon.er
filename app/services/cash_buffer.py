"""
Cash Buffer Recommendation Engine for FINHYPE.

Translates mutual fund net flow forecasts and prediction intervals into actionable,
transparent liquidity buffer recommendations for Liquid and Overnight fund treasuries.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BufferRecommendation:
    """Structured cash buffer recommendation payload."""
    category: str
    horizon_months: int
    risk_tolerance: str
    confidence_level_pct: float
    recommended_buffer_cr: float
    recommended_buffer_pct_aum: float
    base_operational_buffer_cr: float
    cumulative_downside_deficit_cr: float
    cumulative_point_forecast_cr: float
    uncertainty_safety_margin_cr: float
    preferred_model: str
    historical_backtest_coverage_pct: float
    monthly_breakdown: List[Dict[str, Any]]
    assumptions: Dict[str, Any]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_preferred_model(category: str, horizon: int) -> str:
    """
    Select the empirical top-performing model based on Phase 4 backtest evidence:
    - Liquid Funds: SARIMAX across all horizons (h=1, 2, 3).
    - Overnight Funds: SARIMAX at horizon 1; Seasonal-Naive at horizons 2 and 3.
    """
    cat_lower = category.lower()
    if "liquid" in cat_lower:
        return "sarimax"
    else:  # Overnight
        if horizon == 1:
            return "sarimax"
        else:
            return "seasonal_naive"


def get_default_base_buffer_pct(category: str) -> float:
    """
    Default baseline operational liquidity percentage of AUM:
    - Liquid Funds: 5.0%
    - Overnight Funds: 2.5%
    """
    if "liquid" in category.lower():
        return 5.0
    return 2.5


def calculate_cash_buffer_recommendation(
    category: str,
    horizon_months: int,
    forecast_flows: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Optional[Sequence[float]] = None,
    current_aum: float = 100000.0,
    risk_tolerance: str = "moderate",
    base_buffer_pct: Optional[float] = None,
    model_name: Optional[str] = None,
    historical_backtest_coverage: Optional[float] = None,
) -> BufferRecommendation:
    """
    Calculate cash buffer recommendation for planning horizon (1, 2, or 3 months).
    
    Formula:
    Recommended Buffer = max(Base Operational Buffer, Peak Cumulative Downside Deficit)
    where:
    Base Operational Buffer = base_buffer_pct * current_aum
    Cumulative Deficit_k = max(0, -sum_{j=1}^k lower_bound_j)
    Peak Cumulative Deficit = max_{k=1..h} Cumulative Deficit_k
    """
    if horizon_months not in [1, 2, 3]:
        raise ValueError(f"horizon_months must be 1, 2, or 3; got {horizon_months}")
        
    if len(forecast_flows) < horizon_months:
        raise ValueError(
            f"forecast_flows length ({len(forecast_flows)}) is less than requested horizon ({horizon_months})"
        )
    if len(lower_bounds) < horizon_months:
        raise ValueError(
            f"lower_bounds length ({len(lower_bounds)}) is less than requested horizon ({horizon_months})"
        )
        
    if current_aum is None or not np.isfinite(current_aum) or current_aum <= 0:
        raise ValueError(f"current_aum must be positive and finite; got {current_aum}")
        
    if base_buffer_pct is not None and (not np.isfinite(base_buffer_pct) or base_buffer_pct < 0):
        raise ValueError(f"base_buffer_pct must be non-negative and finite; got {base_buffer_pct}")
        
    for k in range(horizon_months):
        if not np.isfinite(forecast_flows[k]):
            raise ValueError(f"forecast_flows contains non-finite value at index {k}: {forecast_flows[k]}")
        if not np.isfinite(lower_bounds[k]):
            raise ValueError(f"lower_bounds contains non-finite value at index {k}: {lower_bounds[k]}")
        if upper_bounds is not None and len(upper_bounds) > k and not np.isfinite(upper_bounds[k]):
            raise ValueError(f"upper_bounds contains non-finite value at index {k}: {upper_bounds[k]}")

    risk_tol = risk_tolerance.lower().strip()
    if risk_tol in ["conservative", "95", "95%"]:
        confidence_pct = 95.0
    elif risk_tol in ["moderate", "80", "80%"]:
        confidence_pct = 80.0
    elif risk_tol in ["aggressive", "expected"]:
        confidence_pct = 50.0
    else:
        confidence_pct = 80.0
        risk_tol = "moderate"
        
    if base_buffer_pct is None:
        base_buffer_pct = get_default_base_buffer_pct(category)
        
    if model_name is None:
        model_name = get_preferred_model(category, horizon_months)
        
    # Base operational cushion
    base_op_buffer = round((base_buffer_pct / 100.0) * current_aum, 2)
    
    # Calculate monthly and cumulative deficits
    monthly_breakdown: List[Dict[str, Any]] = []
    cum_forecast = 0.0
    cum_downside = 0.0
    peak_deficit = 0.0
    
    # Warnings list
    warnings: List[str] = []
    
    for k in range(horizon_months):
        step = k + 1
        pt_f = float(forecast_flows[k])
        lb = float(lower_bounds[k])
        ub = float(upper_bounds[k]) if upper_bounds is not None and len(upper_bounds) > k else pt_f + abs(pt_f - lb)
        
        # Risk adjustment
        # If aggressive (50%), use point forecast as baseline downside
        effective_downside = pt_f if risk_tol == "aggressive" else lb
        
        cum_forecast += pt_f
        cum_downside += effective_downside
        
        # Cumulative deficit: positive shortfall if cum_downside is negative
        cum_deficit = max(0.0, -cum_downside)
        if cum_deficit > peak_deficit:
            peak_deficit = cum_deficit
            
        monthly_breakdown.append({
            "month_step": step,
            "forecast_net_flow_cr": round(pt_f, 2),
            "lower_bound_cr": round(lb, 2),
            "upper_bound_cr": round(ub, 2),
            "effective_downside_cr": round(effective_downside, 2),
            "cumulative_forecast_cr": round(cum_forecast, 2),
            "cumulative_downside_cr": round(cum_downside, 2),
            "cumulative_deficit_cr": round(cum_deficit, 2),
        })
        
    # Recommended buffer is the maximum of the operational floor and peak downside deficit
    recommended_buffer = max(base_op_buffer, peak_deficit)
    recommended_pct_aum = round((recommended_buffer / current_aum) * 100.0, 2)
    
    # Uncertainty safety margin (difference between peak downside deficit and negative expected flow)
    expected_deficit = max(0.0, -cum_forecast)
    safety_margin = max(0.0, round(peak_deficit - expected_deficit, 2))
    
    # Default coverage from backtest evidence if not supplied
    if historical_backtest_coverage is None:
        if "liquid" in category.lower():
            historical_backtest_coverage = 79.17 if confidence_pct == 80.0 else 95.83
        else:
            historical_backtest_coverage = 75.00 if confidence_pct == 80.0 else 87.50
            
    # Add disclaimers and warnings
    warnings.append(
        "Advisory buffer only. Does not constitute a financial guarantee against extreme tail-risk liquidity shocks or intraday corporate runs."
    )
    if horizon_months > 1:
        warnings.append(
            f"Multi-month planning horizon ({horizon_months}M) uses conservative comonotonic deficit aggregation (assuming consecutive adverse shocks), not a calibrated multi-month joint prediction interval."
        )
    if "overnight" in category.lower() and horizon_months > 1 and model_name == "seasonal_naive":
        warnings.append(
            "Seasonal-Naive persistence is selected for Overnight Funds beyond Horizon 1 based on backtest evidence. "
            "Projections and buffer requirements are highly sensitive to the November 2025 historical outlier (-₹37,624.53 Cr)."
        )
    if peak_deficit > (0.25 * current_aum):
        warnings.append(
            f"High liquidity risk detected: Projected peak deficit (₹{peak_deficit:,.2f} Cr) exceeds 25% of fund AUM."
        )
        
    downside_cov = "90.0%" if confidence_pct == 80.0 else ("97.5%" if confidence_pct == 95.0 else "50.0%")
    assumptions = {
        "base_operational_buffer_pct": base_buffer_pct,
        "current_aum_cr": current_aum,
        "risk_tolerance_profile": risk_tol,
        "nominal_confidence_level": f"{confidence_pct}% two-sided interval ({downside_cov} one-sided downside coverage)",
        "macro_policy_rate_assumption": "Constant forward rate (Delta Repo = 0)",
        "aggregation_rule": "Peak cumulative downside deficit over planning horizon (conservative comonotonic scenario)",
    }
    
    return BufferRecommendation(
        category=category,
        horizon_months=horizon_months,
        risk_tolerance=risk_tol,
        confidence_level_pct=confidence_pct,
        recommended_buffer_cr=round(recommended_buffer, 2),
        recommended_buffer_pct_aum=recommended_pct_aum,
        base_operational_buffer_cr=base_op_buffer,
        cumulative_downside_deficit_cr=round(peak_deficit, 2),
        cumulative_point_forecast_cr=round(cum_forecast, 2),
        uncertainty_safety_margin_cr=safety_margin,
        preferred_model=model_name,
        historical_backtest_coverage_pct=historical_backtest_coverage,
        monthly_breakdown=monthly_breakdown,
        assumptions=assumptions,
        warnings=warnings,
    )

