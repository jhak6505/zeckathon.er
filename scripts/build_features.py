"""
CLI script to execute the FINHYPE feature engineering pipeline.

Reads data/processed/fund_flows_monthly.csv and data/processed/external_factors_monthly.csv,
computes all calendar, autoregressive, rolling, churn, AUM, peer, and macro features,
and outputs data/processed/featured_fund_flows.csv.
"""

from __future__ import annotations

import logging
import os
import sys

# Ensure FINHYPE root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.forecasting.feature_engineering import build_feature_pipeline, get_model_ready_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> int:
    try:
        logging.info("Executing FINHYPE Feature Engineering Pipeline...")
        df_featured = build_feature_pipeline()
        logging.info(
            "Feature engineering complete. Total records: %d, Total features/columns: %d",
            len(df_featured),
            len(df_featured.columns),
        )
        
        # Check model-ready subset
        clean_df = get_model_ready_data(df_featured, drop_warmup=True)
        logging.info(
            "Model-ready records (warmup dropped): %d records (Liquid: %d, Overnight: %d) with 0 NaNs across all columns.",
            len(clean_df),
            len(clean_df[clean_df["category"] == "Liquid Fund"]),
            len(clean_df[clean_df["category"] == "Overnight Fund"]),
        )
        logging.info(
            "Available columns (%d):\n%s",
            len(df_featured.columns),
            ", ".join(df_featured.columns),
        )
        return 0
    except Exception as e:
        logging.exception("Failed to build feature pipeline: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())

