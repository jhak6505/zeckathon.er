"""
Unit tests for app.forecasting.eda module.

Validates:
1. Summary stats calculation (mean, std, median, turnover).
2. Quarter-end comparison logic and divergence.
3. Monthly seasonality table format and column outputs.
4. Outlier detection logic and z-score filtering.
5. Interactive plot generation to HTML without errors.
"""

from __future__ import annotations

import os
import pandas as pd
import pytest

from app.forecasting.eda import (
    compute_category_summary_stats,
    compute_monthly_seasonality,
    compute_quarter_end_comparison,
    detect_outliers,
    plot_category_cross_correlation,
    plot_gross_flows_comparison,
    plot_net_flows_time_series,
    plot_outlier_analysis,
    plot_quarter_end_effect,
    plot_seasonality_calendar_month,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Load processed fund flows dataset."""
    return pd.read_csv("data/processed/fund_flows_monthly.csv")


def test_compute_category_summary_stats(sample_df):
    """Verify summary statistics for both fund categories."""
    stats = compute_category_summary_stats(sample_df)
    assert len(stats) == 2
    assert set(stats["category"].tolist()) == {"Liquid Fund", "Overnight Fund"}
    
    liq = stats[stats["category"] == "Liquid Fund"].iloc[0]
    ovn = stats[stats["category"] == "Overnight Fund"].iloc[0]
    
    assert liq["months_count"] == 90
    assert ovn["months_count"] == 90
    
    # Liquid flow volatility should be significantly larger than Overnight
    assert liq["net_flow_std_cr"] > ovn["net_flow_std_cr"]
    # Turnover ratio check
    assert liq["avg_turnover_ratio"] > 0
    assert ovn["avg_turnover_ratio"] > 2.0  # Overnight turns over multiple times its AUM


def test_compute_quarter_end_comparison(sample_df):
    """Verify quarter end metrics show net negative drag."""
    qe_stats = compute_quarter_end_comparison(sample_df)
    assert len(qe_stats) == 2
    
    liq = qe_stats[qe_stats["category"] == "Liquid Fund"].iloc[0]
    # Quarter-end mean net flow must be negative due to corporate advance tax
    assert liq["qe_mean_net_flow_cr"] < 0
    # Non-quarter-end mean net flow must be positive
    assert liq["non_qe_mean_net_flow_cr"] > 0
    # Difference should be substantial negative drag
    assert liq["diff_qe_minus_non_qe_cr"] < -50000


def test_compute_monthly_seasonality(sample_df):
    """Verify 12 calendar months are generated."""
    season_df = compute_monthly_seasonality(sample_df)
    assert len(season_df) == 12
    assert season_df["month_num"].tolist() == list(range(1, 13))
    assert "liquid_mean_net_flow_cr" in season_df.columns
    assert "overnight_mean_net_flow_cr" in season_df.columns
    
    # March (month 3) must be strongly negative
    march = season_df[season_df["month_num"] == 3].iloc[0]
    assert march["liquid_mean_net_flow_cr"] < -50000
    # April (month 4) must be strongly positive
    april = season_df[season_df["month_num"] == 4].iloc[0]
    assert april["liquid_mean_net_flow_cr"] > 50000


def test_detect_outliers(sample_df):
    """Verify outlier detection returns valid extreme months."""
    outliers = detect_outliers(sample_df, z_threshold=2.0)
    assert not outliers.empty
    assert "month" in outliers.columns
    assert "z_score" in outliers.columns
    assert "type" in outliers.columns
    assert (outliers["z_score"].abs() >= 2.0).all()


def test_plot_generation(sample_df, tmp_path):
    """Verify all 6 Plotly visualizers generate valid HTML files."""
    output_1 = str(tmp_path / "plot1.html")
    output_2 = str(tmp_path / "plot2.html")
    output_3 = str(tmp_path / "plot3.html")
    output_4 = str(tmp_path / "plot4.html")
    output_5 = str(tmp_path / "plot5.html")
    output_6 = str(tmp_path / "plot6.html")
    
    plot_net_flows_time_series(sample_df, output_1)
    plot_gross_flows_comparison(sample_df, output_2)
    plot_seasonality_calendar_month(sample_df, output_3)
    plot_quarter_end_effect(sample_df, output_4)
    plot_outlier_analysis(sample_df, output_5)
    plot_category_cross_correlation(sample_df, output_6)
    
    for path in [output_1, output_2, output_3, output_4, output_5, output_6]:
        assert os.path.exists(path)
        assert os.path.getsize(path) > 1000

