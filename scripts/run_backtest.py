"""
CLI runner for FINHYPE Phase 4 Rolling-Origin Backtesting.

Executes expanding-window backtest over 24 forecast origins (July 2024 through June 2026),
generates forecast evaluations, prediction intervals, and benchmark comparisons,
and outputs data/processed/backtest_results.csv and data/processed/backtest_metrics_summary.csv.
"""

from __future__ import annotations

import logging
import os
import sys

# Ensure FINHYPE root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from app.forecasting.backtest import run_rolling_origin_backtest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def print_formatted_summary(summary_df: pd.DataFrame) -> None:
    """Print readable tables comparing models across categories and horizons."""
    for category in summary_df["category"].unique():
        print(f"\n=======================================================")
        print(f"   BACKTEST RESULTS: {category.upper()}")
        print(f"=======================================================")
        cat_sub = summary_df[summary_df["category"] == category]
        
        display_cols = [
            "model_name", "horizon", "mae_cr", "rmse_cr", "wape_pct",
            "mape_pct", "mase", "coverage_80_pct", "coverage_95_pct",
            "rel_mae", "skill_score", "fallbacks_count"
        ]
        
        try:
            table_str = cat_sub[display_cols].to_markdown(index=False)
        except Exception:
            table_str = cat_sub[display_cols].to_string(index=False)
            
        print(table_str)


def main() -> int:
    try:
        logging.info("Starting FINHYPE Phase 4 Rolling-Origin Backtest Execution...")
        results_df, summary_df = run_rolling_origin_backtest()
        
        logging.info("Backtest complete!")
        logging.info("Detailed forecasts count: %d rows (Expected: 576)", len(results_df))
        logging.info("Summary metrics count: %d rows", len(summary_df))
        
        # Data integrity checks
        null_counts = results_df[["actual_cr", "predicted_cr", "lower_80", "upper_80", "lower_95", "upper_95"]].isnull().sum()
        if null_counts.sum() > 0:
            logging.error("Null values detected in backtest results:\n%s", null_counts)
            return 1
            
        # Interval ordering check
        inv_80 = (results_df["lower_80"] > results_df["upper_80"]).sum()
        inv_95 = (results_df["lower_95"] > results_df["upper_95"]).sum()
        inv_nest = (results_df["lower_95"] > results_df["lower_80"]).sum() + (results_df["upper_95"] < results_df["upper_80"]).sum()
        
        if inv_80 > 0 or inv_95 > 0 or inv_nest > 0:
            logging.error("Interval consistency check failed: inv_80=%d, inv_95=%d, inv_nest=%d", inv_80, inv_95, inv_nest)
            return 1
            
        logging.info("Interval consistency verified: 100% valid bounds.")
        
        # Print formatted markdown summary
        print_formatted_summary(summary_df)
        return 0
    except Exception as e:
        logging.exception("Backtest execution failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
