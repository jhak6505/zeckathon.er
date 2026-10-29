"""
Script to fetch and generate external factor datasets (RBI Repo Rate and Nifty 50).
"""

from __future__ import annotations

import logging
import os
import sys

# Ensure FINHYPE root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.data.external_factors import build_external_factors_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main() -> int:
    try:
        logging.info("Building external factors dataset (2019-04 to 2026-09)...")
        df = build_external_factors_dataset()
        logging.info("Successfully generated external factors dataset: %d months.", len(df))
        logging.info("Sample preview:\n%s", df.head(5).to_string())
        return 0
    except Exception as e:
        logging.exception("Error building external factors: %s", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
