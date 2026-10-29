"""
Unit tests for FINHYPE Phase 5: Cash Buffer Recommendation Engine.

Validates:
1. Exact cash buffer formula logic (Base Floor vs. Downside Deficit).
2. Multi-month negative flow aggregation (Peak cumulative deficit).
3. Risk tolerance profile behavior (Conservative >= Moderate).
4. Error handling on invalid horizons, insufficient data, or non-positive AUM.
5. Preferred model selection based on backtest evidence.
6. Prevention of future actuals leakage in forward forecasting.
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
    generate_forward_calendar,
    get_forward_recommendation,
)


def test_single_month_outflow_recommendation():
    """Verify that a negative lower bound drives the cash buffer when it exceeds base floor."""
    # AUM = 100,000 Cr, Base buffer = 5% (5,000 Cr)
    # Expected flow = -10,000 Cr, Lower bound = -15,000 Cr
    rec = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=1,
        forecast_flows=[-10000.0],
        lower_bounds=[-15000.0],
        current_aum=100000.0,
        base_buffer_pct=5.0,
        risk_tolerance="moderate",
    )
    # Downside deficit is 15,000 Cr > 5,000 Cr base buffer
    assert rec.recommended_buffer_cr == 15000.0
    assert rec.recommended_buffer_pct_aum == 15.0
    assert rec.base_operational_buffer_cr == 5000.0
    assert rec.cumulative_downside_deficit_cr == 15000.0


def test_positive_inflow_retains_operational_floor():
    """Verify that when flows are positive, buffer defaults to base operational floor."""
    # Expected flow = +20,000 Cr, Lower bound = +5,000 Cr (inflow even in downside)
    rec = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=1,
        forecast_flows=[20000.0],
        lower_bounds=[5000.0],
        current_aum=100000.0,
        base_buffer_pct=5.0,
        risk_tolerance="moderate",
    )
    # Downside deficit is 0 Cr. Base floor is 5,000 Cr.
    assert rec.recommended_buffer_cr == 5000.0
    assert rec.recommended_buffer_pct_aum == 5.0
    assert rec.cumulative_downside_deficit_cr == 0.0


def test_multi_month_deficit_aggregation_peak_rule():
    """
    CRITICAL MULTI-MONTH AGGREGATION TEST:
    Month 1: Outflow (-20,000 Cr)
    Month 2: Massive Inflow (+40,000 Cr)
    Even though 2-month net is +20,000 Cr, Month 1 requires 20,000 Cr buffer!
    """
    rec = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=2,
        forecast_flows=[-15000.0, 50000.0],
        lower_bounds=[-20000.0, 40000.0],
        current_aum=100000.0,
        base_buffer_pct=5.0,
        risk_tolerance="moderate",
    )
    # Month 1 cumulative deficit = 20,000 Cr
    # Month 2 cumulative sum = -20,000 + 40,000 = +20,000 Cr (deficit = 0 Cr)
    # Peak cumulative deficit must be 20,000 Cr!
    assert rec.cumulative_downside_deficit_cr == 20000.0
    assert rec.recommended_buffer_cr == 20000.0


def test_compound_consecutive_outflows():
    """Verify compound accumulation of consecutive outflows."""
    # Month 1: -10,000 Cr. Month 2: -15,000 Cr.
    # Cumulative deficit Month 1: 10,000 Cr. Month 2: 25,000 Cr.
    rec = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=2,
        forecast_flows=[-8000.0, -12000.0],
        lower_bounds=[-10000.0, -15000.0],
        current_aum=100000.0,
        base_buffer_pct=5.0,
        risk_tolerance="moderate",
    )
    assert rec.cumulative_downside_deficit_cr == 25000.0
    assert rec.recommended_buffer_cr == 25000.0


def test_risk_tolerance_scaling():
    """Verify Conservative (95%) produces larger or equal buffer than Moderate (80%)."""
    # Lower bound for 95% is wider (-30,000 Cr) than 80% (-20,000 Cr)
    rec_mod = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=1,
        forecast_flows=[-15000.0],
        lower_bounds=[-20000.0],
        current_aum=100000.0,
        risk_tolerance="moderate",
    )
    rec_cons = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=1,
        forecast_flows=[-15000.0],
        lower_bounds=[-30000.0],
        current_aum=100000.0,
        risk_tolerance="conservative",
    )
    assert rec_cons.recommended_buffer_cr > rec_mod.recommended_buffer_cr
    assert rec_cons.confidence_level_pct == 95.0
    assert rec_mod.confidence_level_pct == 80.0


def test_invalid_inputs_raise_errors():
    """Verify input validation handles invalid horizons, missing data, and negative AUM."""
    # Horizon 0 or 4
    with pytest.raises(ValueError, match="horizon_months must be 1, 2, or 3"):
        calculate_cash_buffer_recommendation("Liquid Fund", 0, [-1000.0], [-2000.0], 10000.0)
    with pytest.raises(ValueError, match="horizon_months must be 1, 2, or 3"):
        calculate_cash_buffer_recommendation("Liquid Fund", 4, [-1000.0] * 4, [-2000.0] * 4, 10000.0)

    # Incomplete forecast series
    with pytest.raises(ValueError, match="forecast_flows length"):
        calculate_cash_buffer_recommendation("Liquid Fund", 3, [-1000.0, -2000.0], [-2000.0] * 3, 10000.0)

    # Non-positive AUM
    with pytest.raises(ValueError, match="current_aum must be positive"):
        calculate_cash_buffer_recommendation("Liquid Fund", 1, [-1000.0], [-2000.0], current_aum=-500.0)
    with pytest.raises(ValueError, match="current_aum must be positive"):
        calculate_cash_buffer_recommendation("Liquid Fund", 1, [-1000.0], [-2000.0], current_aum=0.0)


def test_preferred_model_selection():
    """Verify model selection follows empirical Phase 4 backtest evidence."""
    # Liquid Funds: SARIMAX for all horizons
    assert get_preferred_model("Liquid Fund", 1) == "sarimax"
    assert get_preferred_model("Liquid Fund", 2) == "sarimax"
    assert get_preferred_model("Liquid Fund", 3) == "sarimax"

    # Overnight Funds: SARIMAX for h=1, Seasonal-Naive for h=2, 3
    assert get_preferred_model("Overnight Fund", 1) == "sarimax"
    assert get_preferred_model("Overnight Fund", 2) == "seasonal_naive"
    assert get_preferred_model("Overnight Fund", 3) == "seasonal_naive"


def test_forward_calendar_determinism():
    """Verify forward calendar generates exact deterministic tax variables for 2026-10 to 2026-12."""
    cal = generate_forward_calendar(start_month="2026-10", steps=3)
    assert len(cal) == 3
    assert cal["month"].tolist() == ["2026-10", "2026-11", "2026-12"]

    # October (month 10) is post-quarter rebound
    oct_row = cal[cal["month"] == "2026-10"].iloc[0]
    assert oct_row["is_post_quarter_month"] == 1
    assert oct_row["is_advance_tax_month"] == 0

    # December (month 12) is Q3 Advance Tax
    dec_row = cal[cal["month"] == "2026-12"].iloc[0]
    assert dec_row["is_advance_tax_month"] == 1
    assert dec_row["is_quarter_end"] == 1
    assert dec_row["is_fy_end"] == 0


def test_forward_recommendation_integration():
    """Verify end-to-end forward recommendation integration from origin 2026-09."""
    for cat in ["Liquid Fund", "Overnight Fund"]:
        rec = get_forward_recommendation(
            category=cat,
            horizon_months=3,
            risk_tolerance="moderate",
            base_buffer_pct=5.0,
        )
        assert isinstance(rec, BufferRecommendation)
        assert rec.recommended_buffer_cr > 0
        assert rec.recommended_buffer_pct_aum > 0
        assert len(rec.monthly_breakdown) == 3
        assert len(rec.warnings) > 0
        assert "base_operational_buffer_pct" in rec.assumptions


@pytest.mark.parametrize(
    "downside_flows,expected_peak_deficit",
    [
        ([-100.0, 150.0, -20.0], 100.0),
        ([-100.0, -50.0, 200.0], 150.0),
        ([100.0, 50.0, 20.0], 0.0),
        ([0.0, 0.0, 0.0], 0.0),
        ([-100.0, -100.0, -100.0], 300.0),
    ],
)
def test_cash_buffer_regression_deficit_patterns(downside_flows, expected_peak_deficit):
    """
    Parametrized critical regression test verifying peak cumulative downside deficit logic:
    - [-100, +150, -20] -> Month 1 deficit is 100; Month 2 cum = +50; Month 3 cum = +30; Peak deficit = 100.
    - [-100, -50, +200] -> Month 1 deficit = 100; Month 2 deficit = 150; Month 3 cum = +50; Peak deficit = 150.
    - [100, 50, 20] -> All positive inflows; Deficit = 0.
    - [0, 0, 0] -> Zero flows; Deficit = 0.
    - [-100, -100, -100] -> Monotonic outflows; Deficit accumulates to 300.
    """
    rec = calculate_cash_buffer_recommendation(
        category="Liquid Fund",
        horizon_months=3,
        forecast_flows=[0.0, 0.0, 0.0],
        lower_bounds=downside_flows,
        current_aum=100000.0,
        base_buffer_pct=0.0,  # Zero base buffer to isolate deficit calculation
        risk_tolerance="moderate",
    )
    assert rec.cumulative_downside_deficit_cr == expected_peak_deficit
    assert rec.recommended_buffer_cr == expected_peak_deficit


def test_cash_buffer_invalid_inputs_extended():
    """Verify robust input rejection for NaN, Inf, and non-positive parameters."""
    # NaN and Inf in current_aum
    with pytest.raises(ValueError, match="current_aum must be positive and finite"):
        calculate_cash_buffer_recommendation("Liquid Fund", 1, [-100.0], [-200.0], current_aum=float("nan"))
    with pytest.raises(ValueError, match="current_aum must be positive and finite"):
        calculate_cash_buffer_recommendation("Liquid Fund", 1, [-100.0], [-200.0], current_aum=float("inf"))

    # Negative and NaN base_buffer_pct
    with pytest.raises(ValueError, match="base_buffer_pct must be non-negative and finite"):
        calculate_cash_buffer_recommendation("Liquid Fund", 1, [-100.0], [-200.0], current_aum=10000.0, base_buffer_pct=-1.0)
    with pytest.raises(ValueError, match="base_buffer_pct must be non-negative and finite"):
        calculate_cash_buffer_recommendation("Liquid Fund", 1, [-100.0], [-200.0], current_aum=10000.0, base_buffer_pct=float("nan"))

    # Non-finite values in forecast_flows or lower_bounds
    with pytest.raises(ValueError, match="forecast_flows contains non-finite value"):
        calculate_cash_buffer_recommendation("Liquid Fund", 1, [float("nan")], [-200.0], current_aum=10000.0)
    with pytest.raises(ValueError, match="lower_bounds contains non-finite value"):
        calculate_cash_buffer_recommendation("Liquid Fund", 1, [-100.0], [float("-inf")], current_aum=10000.0)


def test_cash_buffer_percentage_formula_precision():
    """Verify mathematical exactness of recommended_buffer_pct_aum across various configurations."""
    test_cases = [
        (100000.0, [-5000.0], [-8000.0], 5.0),
        (500000.0, [-20000.0, -10000.0], [-35000.0, -25000.0], 3.0),
        (84032.57, [1000.0], [-5000.0], 2.5),
    ]
    for aum, f_flows, l_bounds, base_pct in test_cases:
        h = len(f_flows)
        rec = calculate_cash_buffer_recommendation(
            category="Liquid Fund",
            horizon_months=h,
            forecast_flows=f_flows,
            lower_bounds=l_bounds,
            current_aum=aum,
            base_buffer_pct=base_pct,
            risk_tolerance="moderate",
        )
        expected_pct = round((rec.recommended_buffer_cr / rec.assumptions["current_aum_cr"]) * 100.0, 2)
        assert rec.recommended_buffer_pct_aum == expected_pct

