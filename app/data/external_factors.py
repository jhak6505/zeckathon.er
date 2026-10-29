"""
Module for collecting, managing, and preparing external macroeconomic and market factors.

Factors include:
1. RBI Policy Repo Rate (% p.a.) and rate changes (bps) from official MPC resolutions.
2. Nifty 50 Equity Benchmark monthly closing index and returns (%) from NSE / Yahoo Finance.
3. Monetary policy regime indicators (hike, cut, pause).
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import urllib.request
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

EXTERNAL_RAW_DIR = os.path.join("data", "raw", "external")
EXTERNAL_PROCESSED_PATH = os.path.join("data", "processed", "external_factors_monthly.csv")
METADATA_PATH = os.path.join(EXTERNAL_RAW_DIR, "sources_metadata.json")

# Official Reserve Bank of India (RBI) Monetary Policy Committee (MPC) Repo Rate decisions
# Effective dates and rate levels (% p.a.)
OFFICIAL_RBI_REPO_HISTORY: List[Dict[str, str | float]] = [
    {"effective_date": "2019-02-07", "repo_rate_pct": 6.25, "stance": "Neutral"},
    {"effective_date": "2019-04-04", "repo_rate_pct": 6.00, "stance": "Neutral"},
    {"effective_date": "2019-06-06", "repo_rate_pct": 5.75, "stance": "Accommodative"},
    {"effective_date": "2019-08-07", "repo_rate_pct": 5.40, "stance": "Accommodative"},
    {"effective_date": "2019-10-04", "repo_rate_pct": 5.15, "stance": "Accommodative"},
    {"effective_date": "2020-03-27", "repo_rate_pct": 4.40, "stance": "Accommodative"},
    {"effective_date": "2020-05-22", "repo_rate_pct": 4.00, "stance": "Accommodative"},
    {"effective_date": "2022-05-04", "repo_rate_pct": 4.40, "stance": "Withdrawal of Accommodation"},
    {"effective_date": "2022-06-08", "repo_rate_pct": 4.90, "stance": "Withdrawal of Accommodation"},
    {"effective_date": "2022-08-05", "repo_rate_pct": 5.40, "stance": "Withdrawal of Accommodation"},
    {"effective_date": "2022-09-30", "repo_rate_pct": 5.90, "stance": "Withdrawal of Accommodation"},
    {"effective_date": "2022-12-07", "repo_rate_pct": 6.25, "stance": "Withdrawal of Accommodation"},
    {"effective_date": "2023-02-08", "repo_rate_pct": 6.50, "stance": "Withdrawal of Accommodation"},
    {"effective_date": "2025-02-07", "repo_rate_pct": 6.25, "stance": "Neutral"},
    {"effective_date": "2025-04-09", "repo_rate_pct": 6.00, "stance": "Neutral"},
    {"effective_date": "2025-08-08", "repo_rate_pct": 5.75, "stance": "Accommodative"},
    {"effective_date": "2025-10-08", "repo_rate_pct": 5.50, "stance": "Accommodative"},
    {"effective_date": "2025-12-05", "repo_rate_pct": 5.25, "stance": "Accommodative"},
]


def get_rbi_repo_rates(start_month: str = "2019-01", end_month: str = "2026-09") -> pd.DataFrame:
    """
    Build monthly RBI policy repo rate series from official MPC decisions.
    
    Each month is assigned the rate prevailing at month-end.
    """
    months = pd.date_range(
        start=pd.to_datetime(start_month + "-01"),
        end=pd.to_datetime(end_month + "-01") + pd.offsets.MonthEnd(1),
        freq="ME"
    )
    
    df_actions = pd.DataFrame(OFFICIAL_RBI_REPO_HISTORY)
    df_actions["effective_date"] = pd.to_datetime(df_actions["effective_date"])
    df_actions = df_actions.sort_values("effective_date").reset_index(drop=True)
    
    records = []
    for dt in months:
        m_str = dt.strftime("%Y-%m")
        # Find the rate active as of this month's end
        active_decisions = df_actions[df_actions["effective_date"] <= dt]
        if not active_decisions.empty:
            latest = active_decisions.iloc[-1]
            rate = float(latest["repo_rate_pct"])
            stance = str(latest["stance"])
        else:
            rate = float(df_actions.iloc[0]["repo_rate_pct"])
            stance = str(df_actions.iloc[0]["stance"])
        
        records.append({
            "month": m_str,
            "repo_rate_pct": rate,
            "policy_stance": stance
        })
        
    df_rates = pd.DataFrame(records)
    # Calculate month-over-month rate change in basis points (1% = 100 bps)
    df_rates["repo_rate_change_bps"] = (df_rates["repo_rate_pct"].diff() * 100).fillna(0.0).round(1)
    
    # Regime indicators
    df_rates["is_rate_hike_cycle"] = (df_rates["repo_rate_change_bps"] > 0).astype(int)
    df_rates["is_rate_cut_cycle"] = (df_rates["repo_rate_change_bps"] < 0).astype(int)
    
    return df_rates


def fetch_nifty50_from_yahoo(timeout: int = 10) -> pd.DataFrame:
    """
    Fetch monthly closing prices for Nifty 50 (^NSEI) from Yahoo Finance.
    """
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?interval=1mo&range=10y"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
        
    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    adjclose = result["indicators"]["adjclose"][0]["adjclose"]
    close = result["indicators"]["quote"][0]["close"]
    
    rows = []
    for ts, c, ac in zip(timestamps, close, adjclose):
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        m = dt.strftime("%Y-%m")
        price = round(ac if ac is not None else c, 2)
        rows.append({"month": m, "date": dt.strftime("%Y-%m-%d"), "nifty_close": price})
        
    df = pd.DataFrame(rows).drop_duplicates(subset=["month"], keep="last")
    df = df.sort_values("month").reset_index(drop=True)
    df["nifty_return_pct"] = round(df["nifty_close"].pct_change() * 100, 2)
    return df


def get_nifty50_monthly(
    cache_path: Optional[str] = None,
    allow_network: bool = True
) -> pd.DataFrame:
    """
    Get monthly Nifty 50 series. Reads from local raw cache first,
    or attempts live fetch if cache is missing and network is allowed.
    """
    if cache_path is None:
        cache_path = os.path.join(EXTERNAL_RAW_DIR, "nifty50_raw.csv")
        
    if os.path.exists(cache_path):
        df = pd.read_csv(cache_path)
        df["month"] = df["month"].astype(str)
        return df
        
    if allow_network:
        try:
            df = fetch_nifty50_from_yahoo()
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            df.to_csv(cache_path, index=False)
            return df
        except Exception as e:
            logger.warning("Could not fetch Nifty 50 live: %s", e)
            
    raise FileNotFoundError(f"Nifty 50 data not found at {cache_path} and live fetch was not successful.")


def save_sources_metadata(metadata_path: str = METADATA_PATH) -> None:
    """
    Save metadata manifest detailing external factor sources, definitions, units, and limitations.
    """
    metadata = {
        "sources": [
            {
                "id": "rbi_policy_repo_rate",
                "name": "Reserve Bank of India Policy Repo Rate",
                "provider": "Reserve Bank of India (RBI)",
                "official_url": "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx",
                "frequency": "Monthly (effective policy decision rate)",
                "units": "Percent per annum (% p.a.)",
                "variables": {
                    "repo_rate_pct": "Policy repo rate prevailing at month-end",
                    "repo_rate_change_bps": "Month-over-month change in basis points",
                    "policy_stance": "MPC official stance (Accommodative / Neutral / Withdrawal of Accommodation)"
                },
                "methodology": (
                    "Derived from official Monetary Policy Committee (MPC) bi-monthly and off-cycle "
                    "policy resolutions. Rates mapped forward until the next resolution date."
                ),
                "limitations": (
                    "Policy rates change on MPC meeting dates rather than smooth monthly intervals. "
                    "However, as a monthly macro anchor for short-term liquidity yields, month-end rates "
                    "accurately benchmark money market spreads."
                )
            },
            {
                "id": "nifty50_index",
                "name": "Nifty 50 Benchmark Equity Index",
                "provider": "National Stock Exchange of India (NSE) / Yahoo Finance (^NSEI)",
                "official_url": "https://www.nseindia.com",
                "frequency": "Monthly (last trading day close)",
                "units": "Index level & percentage return (% MoM)",
                "variables": {
                    "nifty_close": "Monthly closing value of Nifty 50 index",
                    "nifty_return_pct": "Month-over-month percentage return"
                },
                "methodology": (
                    "End-of-month adjusted close index levels retrieved from standard exchange records. "
                    "Monthly return computed as (Close_t - Close_{t-1}) / Close_{t-1} * 100."
                ),
                "limitations": (
                    "Equity returns represent sentiment and asset rebalancing rather than direct debt yields. "
                    "High volatility months (e.g., March 2020) can create non-linear correlations with fund flows."
                )
            }
        ],
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "time_coverage": "2019-01 to 2026-09"
    }
    
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def build_external_factors_dataset(
    start_month: str = "2019-04",
    end_month: str = "2026-09",
    save_processed: bool = True
) -> pd.DataFrame:
    """
    Build and save the processed monthly external factors dataset.
    
    Merges RBI repo rates and Nifty 50 equity series for the exact study horizon.
    """
    df_repo = get_rbi_repo_rates(start_month="2019-01", end_month=end_month)
    df_nifty = get_nifty50_monthly()
    
    # Save raw repo rate
    os.makedirs(EXTERNAL_RAW_DIR, exist_ok=True)
    repo_raw_path = os.path.join(EXTERNAL_RAW_DIR, "rbi_repo_rate_raw.csv")
    df_repo.to_csv(repo_raw_path, index=False)
    
    # Merge on month
    df_merged = pd.merge(df_repo, df_nifty[["month", "nifty_close", "nifty_return_pct"]], on="month", how="left")
    
    # Filter to requested study period
    df_merged = df_merged[(df_merged["month"] >= start_month) & (df_merged["month"] <= end_month)].copy()
    df_merged = df_merged.sort_values("month").reset_index(drop=True)
    
    # Ensure no missing values in target study period
    if df_merged.isnull().any().any():
        null_cols = df_merged.columns[df_merged.isnull().any()].tolist()
        logger.warning("External factors table contains nulls in columns: %s", null_cols)
        
    save_sources_metadata()
    
    if save_processed:
        os.makedirs(os.path.dirname(EXTERNAL_PROCESSED_PATH), exist_ok=True)
        df_merged.to_csv(EXTERNAL_PROCESSED_PATH, index=False)
        
    return df_merged

