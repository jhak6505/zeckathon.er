"""
scripts/init_db.py
──────────────────
CLI entrypoint to initialize SQLite database at data/finhype.db
and import records from data/processed/fund_flows_monthly.csv.

Usage:
    python scripts/init_db.py [--db-path data/finhype.db] [--csv-path data/processed/fund_flows_monthly.csv]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.data.db import (
    DEFAULT_CSV_PATH,
    DEFAULT_DB_PATH,
    get_summary,
    import_csv,
    init_db,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="FINHYPE SQLite Database Initializer")
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--csv-path",
        type=str,
        default=str(DEFAULT_CSV_PATH),
        help=f"Path to source CSV (default: {DEFAULT_CSV_PATH})",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    csv_path = Path(args.csv_path)

    logger.info("═══ Phase 2: Database Initialization ═══")
    logger.info("Target DB:  %s", db_path)
    logger.info("Source CSV: %s", csv_path)

    # Step 1: Initialize table
    init_db(db_path=db_path)

    # Step 2: Import CSV
    inserted = import_csv(csv_path=csv_path, db_path=db_path)
    logger.info("New records inserted: %d", inserted)

    # Step 3: Print summary
    summary = get_summary(db_path=db_path)
    separator = "─" * 60
    logger.info("\n%s\nDATABASE SUMMARY\n%s", separator, separator)
    logger.info("Total records:    %d", summary["total_records"])
    logger.info("Date coverage:    %s to %s (%d months)",
                summary["start_month"], summary["end_month"], summary["distinct_months"])
    logger.info("Categories:       %s", ", ".join(summary["categories"]))
    for cat, count in summary["category_counts"].items():
        logger.info("  • %-16s %d rows", cat + ":", count)
    logger.info(separator)


if __name__ == "__main__":
    main()

