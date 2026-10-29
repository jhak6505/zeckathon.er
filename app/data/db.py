"""
app/data/db.py
──────────────
SQLite database backend for FINHYPE.

Manages the local SQLite database (default: data/finhype.db), providing:
  - Table initialization with UNIQUE(month, category) constraint.
  - Safe, idempotent CSV importing from processed monthly reports.
  - Parameterized record retrieval with category and date range filtering.
  - Summary aggregation (record counts, date coverage, category breakdown).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

# Default locations relative to repository root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "finhype.db"
DEFAULT_CSV_PATH = REPO_ROOT / "data" / "processed" / "fund_flows_monthly.csv"

TABLE_NAME = "fund_flows_monthly"


class DatabaseError(Exception):
    """Custom exception raised when a database operation fails."""
    pass


def get_connection(db_path: Union[Path, str] = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Open and return a connection to the SQLite database.
    Ensures parent directories exist and enables sqlite3.Row for dict-like access.
    """
    path = Path(db_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as exc:
        logger.error("Failed to connect to database at '%s': %s", path, exc)
        raise DatabaseError(f"Database connection error: {exc}") from exc


def init_db(db_path: Union[Path, str] = DEFAULT_DB_PATH) -> None:
    """
    Initialize the database schema if it does not already exist.

    Creates:
      - fund_flows_monthly table with UNIQUE(month, category)
      - Indexes on (category, month) and (month) for fast range queries.
    """
    path = Path(db_path)
    logger.info("Initializing database at: %s", path)

    schema_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        month TEXT NOT NULL,
        month_label TEXT,
        month_year INTEGER,
        month_num INTEGER,
        category TEXT NOT NULL,
        funds_mobilised_cr REAL,
        redemption_cr REAL,
        net_inflow_cr REAL,
        aum_cr REAL,
        avg_aum_cr REAL,
        source_file TEXT,
        source_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(month, category)
    );

    CREATE INDEX IF NOT EXISTS idx_fund_flows_cat_month
        ON {TABLE_NAME}(category, month);

    CREATE INDEX IF NOT EXISTS idx_fund_flows_month
        ON {TABLE_NAME}(month);
    """

    conn = get_connection(path)
    try:
        with conn:
            conn.executescript(schema_sql)
        logger.info("Table '%s' and indexes initialized successfully.", TABLE_NAME)
    except sqlite3.Error as exc:
        logger.error("Error creating database schema: %s", exc)
        raise DatabaseError(f"Schema initialization failed: {exc}") from exc
    finally:
        conn.close()


def import_csv(
    csv_path: Union[Path, str] = DEFAULT_CSV_PATH,
    db_path: Union[Path, str] = DEFAULT_DB_PATH,
    on_conflict: str = "ignore",
) -> int:
    """
    Import monthly records from the processed CSV into SQLite.

    Idempotent: Running this multiple times will NOT create duplicate records.
    Uses parameterized queries and handles UNIQUE(month, category) conflicts.

    Args:
        csv_path: Path to processed fund_flows_monthly.csv.
        db_path: Path to target SQLite database.
        on_conflict: "ignore" (skip duplicates, default) or "replace" (update existing).

    Returns:
        Number of newly inserted or affected records.
    """
    c_path = Path(csv_path)
    d_path = Path(db_path)

    if not c_path.exists():
        raise FileNotFoundError(f"Source CSV file not found: {c_path}")

    # Ensure schema exists before importing
    init_db(d_path)

    try:
        df = pd.read_csv(c_path)
    except Exception as exc:
        logger.error("Failed to read CSV at '%s': %s", c_path, exc)
        raise DatabaseError(f"Cannot read source CSV: {exc}") from exc

    if df.empty:
        logger.warning("Source CSV is empty: %s", c_path)
        return 0

    # Ensure required columns are present
    required_cols = [
        "month", "month_label", "month_year", "month_num", "category",
        "funds_mobilised_cr", "redemption_cr", "net_inflow_cr",
        "aum_cr", "avg_aum_cr", "source_file", "source_url"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise DatabaseError(f"CSV missing required columns: {missing}")

    # Validate that critical identifiers (month, category) are present and valid
    invalid_month = df["month"].isna() | df["month"].astype(str).str.strip().isin(["", "nan", "None"])
    if invalid_month.any():
        bad_count = int(invalid_month.sum())
        raise DatabaseError(f"CSV contains {bad_count} row(s) with missing or empty 'month'; import aborted.")

    invalid_cat = df["category"].isna() | df["category"].astype(str).str.strip().isin(["", "nan", "None"])
    if invalid_cat.any():
        bad_count = int(invalid_cat.sum())
        raise DatabaseError(f"CSV contains {bad_count} row(s) with missing or empty 'category'; import aborted.")

    conflict_clause = "OR REPLACE" if on_conflict.lower() == "replace" else "OR IGNORE"
    insert_sql = f"""
    INSERT {conflict_clause} INTO {TABLE_NAME} (
        month, month_label, month_year, month_num, category,
        funds_mobilised_cr, redemption_cr, net_inflow_cr,
        aum_cr, avg_aum_cr, source_file, source_url
    ) VALUES (
        :month, :month_label, :month_year, :month_num, :category,
        :funds_mobilised_cr, :redemption_cr, :net_inflow_cr,
        :aum_cr, :avg_aum_cr, :source_file, :source_url
    )
    """

    # Prepare records converting NaN to None for clean SQLite NULLs
    records = df[required_cols].to_dict(orient="records")
    for r in records:
        for k, v in r.items():
            if pd.isna(v):
                r[k] = None

    conn = get_connection(d_path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        count_before = cur.fetchone()[0]

        with conn:
            cur.executemany(insert_sql, records)

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        count_after = cur.fetchone()[0]

        inserted = count_after - count_before
        logger.info(
            "Import finished for %s: %d processed, %d newly inserted (total in table: %d)",
            c_path.name, len(records), inserted, count_after,
        )
        return inserted
    except sqlite3.Error as exc:
        logger.error("Failed to insert records into '%s': %s", TABLE_NAME, exc)
        raise DatabaseError(f"CSV import failed: {exc}") from exc
    finally:
        conn.close()


def get_records(
    category: Optional[str] = None,
    start_month: Optional[str] = None,
    end_month: Optional[str] = None,
    db_path: Union[Path, str] = DEFAULT_DB_PATH,
    as_dataframe: bool = False,
) -> Union[list[dict[str, Any]], pd.DataFrame]:
    """
    Retrieve monthly fund-flow records filtered by category and date range.
    All filters use parameterized queries.

    Args:
        category: Optional fund category filter (e.g. 'Liquid Fund' or 'Overnight Fund').
                  Matches case-insensitively.
        start_month: Optional earliest month inclusive in 'YYYY-MM' format (e.g. '2020-01').
        end_month: Optional latest month inclusive in 'YYYY-MM' format (e.g. '2022-12').
        db_path: Path to SQLite database.
        as_dataframe: If True, returns a pandas DataFrame; otherwise a list of dicts.

    Returns:
        List of dictionaries (default) or pandas DataFrame ordered by month ASC, category ASC.
    """
    query = f"""
    SELECT id, month, month_label, month_year, month_num, category,
           funds_mobilised_cr, redemption_cr, net_inflow_cr,
           aum_cr, avg_aum_cr, source_file, source_url, created_at
    FROM {TABLE_NAME}
    WHERE 1=1
    """
    params: list[Any] = []

    if category:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category.strip())

    if start_month:
        query += " AND month >= ?"
        params.append(start_month.strip())

    if end_month:
        query += " AND month <= ?"
        params.append(end_month.strip())

    query += " ORDER BY month ASC, category ASC"

    conn = get_connection(db_path)
    try:
        if as_dataframe:
            df = pd.read_sql_query(query, conn, params=params)
            return df

        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as exc:
        logger.error("Error executing query: %s", exc)
        raise DatabaseError(f"Record retrieval failed: {exc}") from exc
    finally:
        conn.close()


def get_records_df(
    category: Optional[str] = None,
    start_month: Optional[str] = None,
    end_month: Optional[str] = None,
    db_path: Union[Path, str] = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """Convenience wrapper around get_records returning a pandas DataFrame."""
    result = get_records(
        category=category,
        start_month=start_month,
        end_month=end_month,
        db_path=db_path,
        as_dataframe=True,
    )
    return result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)


def get_summary(db_path: Union[Path, str] = DEFAULT_DB_PATH) -> dict[str, Any]:
    """
    Calculate and return basic summary statistics from the database.

    Returns:
        dict containing:
          - total_records: Total number of rows in the table.
          - start_month / min_month: Earliest available month ('YYYY-MM') or None.
          - end_month / max_month: Latest available month ('YYYY-MM') or None.
          - distinct_months: Number of unique months present.
          - categories: List of unique fund categories.
          - category_counts: Dict mapping category name to row count.
          - by_category: Dict mapping each category to detailed sub-metrics.
    """
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()

        # Check if table exists
        cur.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE_NAME,)
        )
        if cur.fetchone()[0] == 0:
            return {
                "total_records": 0,
                "start_month": None,
                "end_month": None,
                "min_month": None,
                "max_month": None,
                "distinct_months": 0,
                "categories": [],
                "category_counts": {},
                "by_category": {},
            }

        # Overall summary
        cur.execute(f"""
        SELECT COUNT(*),
               MIN(month),
               MAX(month),
               COUNT(DISTINCT month)
        FROM {TABLE_NAME}
        """)
        total, min_m, max_m, distinct_m = cur.fetchone()

        if total == 0:
            return {
                "total_records": 0,
                "start_month": None,
                "end_month": None,
                "min_month": None,
                "max_month": None,
                "distinct_months": 0,
                "categories": [],
                "category_counts": {},
                "by_category": {},
            }

        # Category breakdown
        cur.execute(f"""
        SELECT category,
               COUNT(*),
               MIN(month),
               MAX(month),
               ROUND(SUM(funds_mobilised_cr), 2),
               ROUND(SUM(redemption_cr), 2),
               ROUND(SUM(net_inflow_cr), 2),
               ROUND(AVG(aum_cr), 2)
        FROM {TABLE_NAME}
        GROUP BY category
        ORDER BY category ASC
        """)
        cat_rows = cur.fetchall()

        categories: list[str] = []
        category_counts: dict[str, int] = {}
        by_category: dict[str, dict[str, Any]] = {}

        for r in cat_rows:
            cat_name = r[0]
            categories.append(cat_name)
            category_counts[cat_name] = r[1]
            by_category[cat_name] = {
                "count": r[1],
                "start_month": r[2],
                "end_month": r[3],
                "total_mobilised_cr": r[4],
                "total_redemption_cr": r[5],
                "total_net_inflow_cr": r[6],
                "avg_aum_cr": r[7],
            }

        return {
            "total_records": total,
            "start_month": min_m,
            "end_month": max_m,
            "min_month": min_m,
            "max_month": max_m,
            "distinct_months": distinct_m,
            "categories": categories,
            "category_counts": category_counts,
            "by_category": by_category,
        }
    except sqlite3.Error as exc:
        logger.error("Error calculating summary: %s", exc)
        raise DatabaseError(f"Failed to calculate summary: {exc}") from exc
    finally:
        conn.close()

