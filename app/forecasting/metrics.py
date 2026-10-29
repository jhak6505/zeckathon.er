"""
Evaluation metrics module for FINHYPE.

Implements standard scale-dependent, scale-independent, quantile, and interval metrics
specifically designed for mutual fund net flows (handling sign changes, zero-crossings,
and origin-specific denominator scaling).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Union

import numpy as np
import pandas as pd


def calculate_mae(
    y_true: Union[np.ndarray, Sequence[float], pd.Series],
    y_pred: Union[np.ndarray, Sequence[float], pd.Series],
) -> float:
    """Calculate Mean Absolute Error in native units (INR Crore)."""
    yt = np.asarray(y_true, dtype=float).ravel()
    yp = np.asarray(y_pred, dtype=float).ravel()
    if len(yt) != len(yp):
        raise ValueError(f"Length mismatch: len(y_true)={len(yt)} != len(y_pred)={len(yp)}")
    if len(yt) == 0:
        return np.nan
    if not (np.all(np.isfinite(yt)) and np.all(np.isfinite(yp))):
        raise ValueError("Input vectors contain non-finite values (NaN or Inf)")
    return float(np.mean(np.abs(yt - yp)))


def calculate_rmse(
    y_true: Union[np.ndarray, Sequence[float], pd.Series],
    y_pred: Union[np.ndarray, Sequence[float], pd.Series],
) -> float:
    """Calculate Root Mean Squared Error in native units (INR Crore)."""
    yt = np.asarray(y_true, dtype=float).ravel()
    yp = np.asarray(y_pred, dtype=float).ravel()
    if len(yt) != len(yp):
        raise ValueError(f"Length mismatch: len(y_true)={len(yt)} != len(y_pred)={len(yp)}")
    if len(yt) == 0:
        return np.nan
    if not (np.all(np.isfinite(yt)) and np.all(np.isfinite(yp))):
        raise ValueError("Input vectors contain non-finite values (NaN or Inf)")
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def calculate_wape(
    y_true: Union[np.ndarray, Sequence[float], pd.Series],
    y_pred: Union[np.ndarray, Sequence[float], pd.Series],
) -> float:
    """
    Calculate Weighted Absolute Percentage Error (WAPE / MAD-to-Mean ratio).
    
    Formula: sum(|y - y_hat|) / sum(|y|)
    Avoids division by individual near-zero actual flows; robust across zero-crossing series.
    Returns value as a percentage (e.g., 25.5 for 25.5%).
    """
    yt = np.asarray(y_true, dtype=float).ravel()
    yp = np.asarray(y_pred, dtype=float).ravel()
    if len(yt) != len(yp):
        raise ValueError(f"Length mismatch: len(y_true)={len(yt)} != len(y_pred)={len(yp)}")
    if len(yt) == 0:
        return np.nan
    if not (np.all(np.isfinite(yt)) and np.all(np.isfinite(yp))):
        raise ValueError("Input vectors contain non-finite values (NaN or Inf)")
    denom = np.sum(np.abs(yt))
    if denom == 0.0:
        return 0.0 if np.all(yt == yp) else np.inf
    return float((np.sum(np.abs(yt - yp)) / denom) * 100.0)


def calculate_epsilon_floor(
    y_train: Union[np.ndarray, Sequence[float], pd.Series],
    percentile: float = 10.0,
    min_floor: float = 100.0,
) -> float:
    """
    Compute origin-specific MAPE denominator floor using ONLY training data up to origin T.
    
    Formula: max(Percentile_{p}(|y_train|), min_floor)
    Strictly prevents forward-looking leakage into error normalization.
    """
    yt = np.asarray(y_train, dtype=float).ravel()
    yt = yt[np.isfinite(yt)]
    if len(yt) == 0:
        return float(min_floor)
    abs_y = np.abs(yt)
    p_val = float(np.percentile(abs_y, percentile))
    return float(max(p_val, min_floor))


def calculate_mape(
    y_true: Union[np.ndarray, Sequence[float], pd.Series],
    y_pred: Union[np.ndarray, Sequence[float], pd.Series],
    epsilon: float = 1000.0,
) -> float:
    """
    Calculate Mean Absolute Percentage Error with an explicit origin-specific floor.
    
    Formula: 100 / n * sum(|y - y_hat| / max(|y|, epsilon))
    
    LIMITATION NOTE:
    Net fund flows cross zero and alternate signs. Even with an epsilon floor,
    percentage error on net flows can misrepresent economic impact because a 
    ₹100 Cr error on a ₹10 Cr net flow has a different operational meaning than 
    a ₹100 Cr error on a ₹100,000 Cr flow. WAPE and MAE are the primary decision metrics.
    """
    yt = np.asarray(y_true, dtype=float).ravel()
    yp = np.asarray(y_pred, dtype=float).ravel()
    if len(yt) != len(yp):
        raise ValueError(f"Length mismatch: len(y_true)={len(yt)} != len(y_pred)={len(yp)}")
    if len(yt) == 0:
        return np.nan
    if not (np.all(np.isfinite(yt)) and np.all(np.isfinite(yp))):
        raise ValueError("Input vectors contain non-finite values (NaN or Inf)")
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError(f"epsilon must be positive and finite; got {epsilon}")
    denom = np.maximum(np.abs(yt), float(epsilon))
    return float(np.mean(np.abs(yt - yp) / denom) * 100.0)


def calculate_mase(
    y_true: Union[np.ndarray, Sequence[float], pd.Series],
    y_pred: Union[np.ndarray, Sequence[float], pd.Series],
    y_train: Union[np.ndarray, Sequence[float], pd.Series],
    seasonal_period: int = 12,
) -> float:
    """
    Calculate Mean Absolute Scaled Error (MASE).
    
    Scale denominator is computed strictly from training data up to origin T:
    scaling = 1 / (T - m) * sum_{t=m+1}^T |y_t - y_{t-m}|
    
    MASE < 1.0 indicates model outperforms the in-sample seasonal naive baseline.
    """
    yt = np.asarray(y_true, dtype=float).ravel()
    yp = np.asarray(y_pred, dtype=float).ravel()
    if len(yt) != len(yp):
        raise ValueError(f"Length mismatch: len(y_true)={len(yt)} != len(y_pred)={len(yp)}")
    y_tr = np.asarray(y_train, dtype=float).ravel()
    y_tr = y_tr[np.isfinite(y_tr)]
    
    if len(yt) == 0 or len(y_tr) == 0:
        return np.nan
    if not (np.all(np.isfinite(yt)) and np.all(np.isfinite(yp))):
        raise ValueError("Input vectors contain non-finite values (NaN or Inf)")
        
    mae = calculate_mae(yt, yp)
    
    if len(y_tr) > seasonal_period:
        # In-sample seasonal naive difference
        scale = float(np.mean(np.abs(y_tr[seasonal_period:] - y_tr[:-seasonal_period])))
    elif len(y_tr) > 1:
        # In-sample non-seasonal difference
        scale = float(np.mean(np.abs(y_tr[1:] - y_tr[:-1])))
    else:
        return np.nan
        
    if scale == 0.0:
        return 0.0 if mae == 0.0 else np.inf
        
    return float(mae / scale)


def calculate_pinball_loss(
    y_true: Union[np.ndarray, Sequence[float], pd.Series],
    q_pred: Union[np.ndarray, Sequence[float], pd.Series],
    alpha: float,
) -> float:
    """
    Calculate Pinball (Quantile) Loss at target quantile alpha in (0, 1).
    
    Formula: max(alpha * (y - q), (1 - alpha) * (q - y))
    """
    if not (0.0 < alpha < 1.0) or not np.isfinite(alpha):
        raise ValueError(f"alpha must be strictly in (0, 1); got {alpha}")
    yt = np.asarray(y_true, dtype=float).ravel()
    qp = np.asarray(q_pred, dtype=float).ravel()
    if len(yt) != len(qp):
        raise ValueError(f"Length mismatch: len(y_true)={len(yt)} != len(q_pred)={len(qp)}")
    if len(yt) == 0:
        return np.nan
    if not (np.all(np.isfinite(yt)) and np.all(np.isfinite(qp))):
        raise ValueError("Input vectors contain non-finite values (NaN or Inf)")
    diff = yt - qp
    loss = np.maximum(alpha * diff, (alpha - 1.0) * diff)
    return float(np.mean(loss))


def calculate_interval_coverage(
    y_true: Union[np.ndarray, Sequence[float], pd.Series],
    lower_bound: Union[np.ndarray, Sequence[float], pd.Series],
    upper_bound: Union[np.ndarray, Sequence[float], pd.Series],
) -> float:
    """
    Calculate empirical interval coverage as a percentage in [0, 100].
    
    Formula: 100 * mean(lower <= y <= upper)
    """
    yt = np.asarray(y_true, dtype=float).ravel()
    lb = np.asarray(lower_bound, dtype=float).ravel()
    ub = np.asarray(upper_bound, dtype=float).ravel()
    if not (len(yt) == len(lb) == len(ub)):
        raise ValueError(
            f"Length mismatch: len(y_true)={len(yt)}, len(lower_bound)={len(lb)}, len(upper_bound)={len(ub)}"
        )
    if len(yt) == 0:
        return np.nan
    if not (np.all(np.isfinite(yt)) and np.all(np.isfinite(lb)) and np.all(np.isfinite(ub))):
        raise ValueError("Input vectors contain non-finite values (NaN or Inf)")
    if np.any(lb > ub):
        raise ValueError("lower_bound exceeds upper_bound at one or more indices")
    covered = (yt >= lb) & (yt <= ub)
    return float(np.mean(covered) * 100.0)


def calculate_interval_width(
    lower_bound: Union[np.ndarray, Sequence[float], pd.Series],
    upper_bound: Union[np.ndarray, Sequence[float], pd.Series],
) -> float:
    """
    Calculate Mean Interval Width (MIW) in native units (INR Crore).
    
    Formula: mean(upper - lower)
    """
    lb = np.asarray(lower_bound, dtype=float).ravel()
    ub = np.asarray(upper_bound, dtype=float).ravel()
    if len(lb) != len(ub):
        raise ValueError(f"Length mismatch: len(lower_bound)={len(lb)} != len(upper_bound)={len(ub)}")
    if len(lb) == 0:
        return np.nan
    if not (np.all(np.isfinite(lb)) and np.all(np.isfinite(ub))):
        raise ValueError("Input vectors contain non-finite values (NaN or Inf)")
    if np.any(lb > ub):
        raise ValueError("lower_bound exceeds upper_bound at one or more indices")
    return float(np.mean(ub - lb))


def calculate_relative_metrics(
    mae_model: float,
    mae_baseline: float,
) -> Dict[str, float]:
    """
    Calculate benchmark-relative performance against Seasonal-Naive baseline.
    
    Relative MAE = MAE_model / MAE_baseline
    Skill Score = 1.0 - (MAE_model / MAE_baseline)
    Skill Score > 0 indicates improvement over seasonal persistence.
    """
    if np.isnan(mae_model) or np.isnan(mae_baseline) or mae_baseline == 0.0:
        return {"rel_mae": np.nan, "skill_score": np.nan}
    rel_mae = float(mae_model / mae_baseline)
    skill_score = float(1.0 - rel_mae)
    return {
        "rel_mae": round(rel_mae, 4),
        "skill_score": round(skill_score, 4),
    }


def compute_all_metrics(
    y_true: Union[np.ndarray, Sequence[float], pd.Series],
    y_pred: Union[np.ndarray, Sequence[float], pd.Series],
    y_train: Union[np.ndarray, Sequence[float], pd.Series],
    lower_80: Optional[Union[np.ndarray, Sequence[float], pd.Series]] = None,
    upper_80: Optional[Union[np.ndarray, Sequence[float], pd.Series]] = None,
    lower_95: Optional[Union[np.ndarray, Sequence[float], pd.Series]] = None,
    upper_95: Optional[Union[np.ndarray, Sequence[float], pd.Series]] = None,
    q_10: Optional[Union[np.ndarray, Sequence[float], pd.Series]] = None,
    q_90: Optional[Union[np.ndarray, Sequence[float], pd.Series]] = None,
    q_025: Optional[Union[np.ndarray, Sequence[float], pd.Series]] = None,
    q_975: Optional[Union[np.ndarray, Sequence[float], pd.Series]] = None,
    epsilon: Optional[float] = None,
    baseline_mae: Optional[float] = None,
) -> Dict[str, float]:
    """
    Compute comprehensive metrics dictionary for point and interval forecasts.
    """
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    
    if epsilon is None:
        epsilon = calculate_epsilon_floor(y_train)
        
    mae = calculate_mae(yt, yp)
    rmse = calculate_rmse(yt, yp)
    wape = calculate_wape(yt, yp)
    mape = calculate_mape(yt, yp, epsilon=epsilon)
    mase = calculate_mase(yt, yp, y_train=y_train)
    
    metrics: Dict[str, float] = {
        "mae_cr": round(mae, 2),
        "rmse_cr": round(rmse, 2),
        "wape_pct": round(wape, 2),
        "mape_pct": round(mape, 2),
        "mase": round(mase, 4),
        "epsilon_floor_cr": round(epsilon, 2),
    }
    
    # 80% Prediction Interval metrics
    if lower_80 is not None and upper_80 is not None:
        metrics["coverage_80_pct"] = round(calculate_interval_coverage(yt, lower_80, upper_80), 2)
        metrics["width_80_cr"] = round(calculate_interval_width(lower_80, upper_80), 2)
        
    # 95% Prediction Interval metrics
    if lower_95 is not None and upper_95 is not None:
        metrics["coverage_95_pct"] = round(calculate_interval_coverage(yt, lower_95, upper_95), 2)
        metrics["width_95_cr"] = round(calculate_interval_width(lower_95, upper_95), 2)
        
    # Pinball Losses
    if q_10 is not None:
        metrics["pinball_loss_q10"] = round(calculate_pinball_loss(yt, q_10, alpha=0.10), 2)
    if q_90 is not None:
        metrics["pinball_loss_q90"] = round(calculate_pinball_loss(yt, q_90, alpha=0.90), 2)
    if q_025 is not None:
        metrics["pinball_loss_q025"] = round(calculate_pinball_loss(yt, q_025, alpha=0.025), 2)
    if q_975 is not None:
        metrics["pinball_loss_q975"] = round(calculate_pinball_loss(yt, q_975, alpha=0.975), 2)
        
    # Relative to Seasonal-Naive Baseline
    if baseline_mae is not None and not np.isnan(baseline_mae):
        rel = calculate_relative_metrics(mae, baseline_mae)
        metrics["rel_mae"] = rel["rel_mae"]
        metrics["skill_score"] = rel["skill_score"]
        
    return metrics

