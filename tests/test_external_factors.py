"""
Unit tests for app.data.external_factors module.
"""

import os
import pandas as pd
import pytest
from app.data.external_factors import (
    build_external_factors_dataset,
    get_nifty50_monthly,
    get_rbi_repo_rates,
    save_sources_metadata,
)


def test_get_rbi_repo_rates_coverage():
    """Verify RBI repo rate generation covers requested months and has valid rates."""
    df = get_rbi_repo_rates(start_month="2019-04", end_month="2026-09")
    assert len(df) == 90
    assert df["month"].iloc[0] == "2019-04"
    assert df["month"].iloc[-1] == "2026-09"
    
    # Check valid Indian policy rates range (4.0% pandemic low to 6.5% peak)
    assert df["repo_rate_pct"].min() >= 4.00
    assert df["repo_rate_pct"].max() <= 6.50
    assert "repo_rate_change_bps" in df.columns
    assert "is_rate_hike_cycle" in df.columns
    assert "is_rate_cut_cycle" in df.columns


def test_rbi_rate_historical_milestones():
    """Verify known RBI MPC decisions match historical record."""
    df = get_rbi_repo_rates(start_month="2019-01", end_month="2026-09")
    df_map = df.set_index("month")["repo_rate_pct"].to_dict()
    
    # April 2019 cut to 6.00%
    assert df_map["2019-04"] == 6.00
    # May 2020 cut to pandemic low 4.00%
    assert df_map["2020-05"] == 4.00
    # April 2022 before hike cycle was 4.00%
    assert df_map["2022-04"] == 4.00
    # June 2022 after hikes
    assert df_map["2022-06"] == 4.90
    # February 2023 peak rate 6.50%
    assert df_map["2023-02"] == 6.50
    # Extended pause throughout 2024
    assert df_map["2024-06"] == 6.50


def test_get_nifty50_monthly():
    """Verify Nifty 50 series contains required fields and valid returns."""
    df = get_nifty50_monthly(allow_network=False)
    assert not df.empty
    assert "month" in df.columns
    assert "nifty_close" in df.columns
    assert "nifty_return_pct" in df.columns
    assert df["nifty_close"].min() > 5000  # Nifty has traded well above 5000 in this decade


def test_build_external_factors_dataset():
    """Verify external factors dataset builds cleanly with 0 nulls for study period."""
    df = build_external_factors_dataset(save_processed=False)
    assert len(df) == 90
    assert df["month"].iloc[0] == "2019-04"
    assert df["month"].iloc[-1] == "2026-09"
    assert df.isnull().sum().sum() == 0


def test_sources_metadata_generation(tmp_path):
    """Verify sources metadata JSON is written and contains documented sources."""
    meta_path = str(tmp_path / "metadata.json")
    save_sources_metadata(metadata_path=meta_path)
    assert os.path.exists(meta_path)
    
    import json
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert "sources" in meta
    assert len(meta["sources"]) >= 2
    source_ids = [s["id"] for s in meta["sources"]]
    assert "rbi_policy_repo_rate" in source_ids
    assert "nifty50_index" in source_ids

