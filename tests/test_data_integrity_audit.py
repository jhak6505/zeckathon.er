"""
Audit and Integration Integrity Tests for FINHYPE.

Validates end-to-end data quality, database constraints, forward forecast artifacts,
mathematical reconciliation, and backtest summary consistency.
"""

from __future__ import annotations

import os
import sqlite3
import numpy as np
import pandas as pd
import pytest

from app.forecasting.metrics import (
    calculate_interval_coverage,
    calculate_mae,
    calculate_rmse,
    calculate_wape,
)


def test_production_fund_flows_completeness_and_continuity():
    """Verify production fund_flows_monthly.csv contains exactly 180 continuous, clean records."""
    csv_path = "data/processed/fund_flows_monthly.csv"
    assert os.path.exists(csv_path), f"Missing dataset: {csv_path}"
    
    df = pd.read_csv(csv_path)
    assert len(df) == 180
    
    # Categories
    categories = sorted(df["category"].unique())
    assert categories == ["Liquid Fund", "Overnight Fund"]
    
    for cat in categories:
        sub = df[df["category"] == cat].sort_values("month").reset_index(drop=True)
        assert len(sub) == 90
        assert sub.loc[0, "month"] == "2019-04"
        assert sub.loc[89, "month"] == "2026-09"
        
        # Check uninterrupted consecutive monthly sequence
        expected_periods = pd.period_range("2019-04", "2026-09", freq="M").strftime("%Y-%m").tolist()
        assert sub["month"].tolist() == expected_periods
        
        # Check zero nulls
        assert sub.isnull().sum().sum() == 0
        
        # Mathematical reconciliation: funds_mobilised - redemption == net_inflow
        recon_diff = (sub["funds_mobilised_cr"] - sub["redemption_cr"]) - sub["net_inflow_cr"]
        assert (recon_diff.abs() < 1e-4).all(), f"Reconciliation failure in {cat}!"


def test_production_sqlite_database_integrity():
    """Verify SQLite database exists, has 180 records, and enforces schema integrity."""
    db_path = "data/finhype.db"
    assert os.path.exists(db_path), f"Missing SQLite database: {db_path}"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check table existence
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fund_flows_monthly'")
    assert cursor.fetchone() is not None
    
    # Total count
    cursor.execute("SELECT COUNT(*) FROM fund_flows_monthly")
    total_count = cursor.fetchone()[0]
    assert total_count == 180
    
    # Check category distribution
    cursor.execute("SELECT category, COUNT(*) FROM fund_flows_monthly GROUP BY category ORDER BY category")
    counts = cursor.fetchall()
    assert counts == [("Liquid Fund", 90), ("Overnight Fund", 90)]
    
    # Unique constraint violation check
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO fund_flows_monthly (month, category, funds_mobilised_cr, redemption_cr, net_inflow_cr, aum_cr)
            VALUES ('2019-04', 'Liquid Fund', 100.0, 100.0, 0.0, 1000.0)
            """
        )
    conn.close()


def test_forward_forecasts_artifact_integrity():
    """Verify generated forward forecast file data format and interval validity."""
    fwd_path = "data/processed/forward_forecasts_3m.csv"
    assert os.path.exists(fwd_path), f"Missing forward forecasts: {fwd_path}"
    
    df = pd.read_csv(fwd_path)
    # 2 categories * 4 models * 3 forecast horizons = 24 rows
    assert len(df) == 24
    assert set(df["target_month"].unique()) == {"2026-10", "2026-11", "2026-12"}
    
    # Interval bounds monotonicity
    assert (df["lower_95"] <= df["lower_80"]).all()
    assert (df["lower_80"] <= df["upper_80"]).all()
    assert (df["upper_80"] <= df["upper_95"]).all()


def test_forward_cash_buffer_recommendations_consistency():
    """Verify dynamic forward cash buffer recommendations match analytical benchmark numbers."""
    from app.services.forward_forecasting import get_forward_recommendation

    # Conservative buffer must be >= Moderate buffer across all categories and horizons
    for cat in ["Liquid Fund", "Overnight Fund"]:
        for h in [1, 2, 3]:
            mod_rec = get_forward_recommendation(category=cat, horizon_months=h, risk_tolerance="moderate")
            cons_rec = get_forward_recommendation(category=cat, horizon_months=h, risk_tolerance="conservative")
            assert cons_rec.recommended_buffer_cr >= mod_rec.recommended_buffer_cr
            
    # Verify Liquid Fund 1M base operational floor
    liq_1m = get_forward_recommendation(category="Liquid Fund", horizon_months=1, risk_tolerance="moderate")
    assert pytest.approx(liq_1m.recommended_buffer_cr, abs=1.0) == 31292.35
    assert liq_1m.recommended_buffer_pct_aum == 5.0
    
    # Verify Overnight Fund 3M sensitivity values (preserving November 2025 outlier)
    ovn_3m_mod = get_forward_recommendation(category="Overnight Fund", horizon_months=3, risk_tolerance="moderate")
    ovn_3m_cons = get_forward_recommendation(category="Overnight Fund", horizon_months=3, risk_tolerance="conservative")
    assert pytest.approx(ovn_3m_mod.recommended_buffer_cr, abs=1.0) == 74130.35
    assert pytest.approx(ovn_3m_cons.recommended_buffer_cr, abs=1.0) == 118049.89


def test_backtest_metrics_recomputation_match():
    """
    Directly recompute backtest metrics from backtest_results.csv and assert exact match
    with backtest_metrics_summary.csv.
    """
    results_path = "data/processed/backtest_results.csv"
    summary_path = "data/processed/backtest_metrics_summary.csv"
    
    res_df = pd.read_csv(results_path)
    sum_df = pd.read_csv(summary_path)
    
    # Test Liquid Fund SARIMAX at Horizon 1
    sub_res = res_df[
        (res_df["category"] == "Liquid Fund") &
        (res_df["model_name"] == "sarimax") &
        (res_df["horizon"] == 1)
    ]
    sub_sum = sum_df[
        (sum_df["category"] == "Liquid Fund") &
        (sum_df["model_name"] == "sarimax") &
        (sum_df["horizon"] == "1")
    ].iloc[0]
    
    recomputed_mae = calculate_mae(sub_res["actual_cr"], sub_res["predicted_cr"])
    recomputed_rmse = calculate_rmse(sub_res["actual_cr"], sub_res["predicted_cr"])
    recomputed_wape = calculate_wape(sub_res["actual_cr"], sub_res["predicted_cr"])
    recomputed_cov80 = calculate_interval_coverage(sub_res["actual_cr"], sub_res["lower_80"], sub_res["upper_80"])
    
    assert pytest.approx(recomputed_mae, abs=0.01) == sub_sum["mae_cr"]
    assert pytest.approx(recomputed_rmse, abs=0.01) == sub_sum["rmse_cr"]
    assert pytest.approx(recomputed_wape, abs=0.01) == sub_sum["wape_pct"]
    assert pytest.approx(recomputed_cov80, abs=0.01) == sub_sum["coverage_80_pct"]
