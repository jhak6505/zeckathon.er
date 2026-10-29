"""
tests/test_db.py
────────────────
Automated unit tests for FINHYPE SQLite database module (app.data.db).

All tests execute against temporary SQLite databases using pytest fixtures.
Never mutates the production database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from app.data.db import (
    DEFAULT_CSV_PATH,
    TABLE_NAME,
    DatabaseError,
    get_connection,
    get_records,
    get_records_df,
    get_summary,
    import_csv,
    init_db,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to an uninitialized temporary SQLite database."""
    return tmp_path / "test_finhype.db"


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create a minimal valid CSV for testing import and constraints."""
    csv_path = tmp_path / "sample_fund_flows.csv"
    data = [
        {
            "month": "2020-01",
            "month_label": "January 2020",
            "month_year": 2020,
            "month_num": 1,
            "category": "Liquid Fund",
            "source_file": "amfi_2020_01.xls",
            "source_url": "https://example.com/amfi_2020_01.xls",
            "funds_mobilised_cr": 100000.0,
            "redemption_cr": 90000.0,
            "net_inflow_cr": 10000.0,
            "aum_cr": 450000.0,
            "avg_aum_cr": 440000.0,
        },
        {
            "month": "2020-01",
            "month_label": "January 2020",
            "month_year": 2020,
            "month_num": 1,
            "category": "Overnight Fund",
            "source_file": "amfi_2020_01.xls",
            "source_url": "https://example.com/amfi_2020_01.xls",
            "funds_mobilised_cr": 50000.0,
            "redemption_cr": 48000.0,
            "net_inflow_cr": 2000.0,
            "aum_cr": 80000.0,
            "avg_aum_cr": 78000.0,
        },
        {
            "month": "2020-02",
            "month_label": "February 2020",
            "month_year": 2020,
            "month_num": 2,
            "category": "Liquid Fund",
            "source_file": "amfi_2020_02.xls",
            "source_url": "https://example.com/amfi_2020_02.xls",
            "funds_mobilised_cr": 110000.0,
            "redemption_cr": 95000.0,
            "net_inflow_cr": 15000.0,
            "aum_cr": 465000.0,
            "avg_aum_cr": 455000.0,
        },
        {
            "month": "2020-02",
            "month_label": "February 2020",
            "month_year": 2020,
            "month_num": 2,
            "category": "Overnight Fund",
            "source_file": "amfi_2020_02.xls",
            "source_url": "https://example.com/amfi_2020_02.xls",
            "funds_mobilised_cr": 55000.0,
            "redemption_cr": 52000.0,
            "net_inflow_cr": 3000.0,
            "aum_cr": 83000.0,
            "avg_aum_cr": 81000.0,
        },
        {
            "month": "2020-03",
            "month_label": "March 2020",
            "month_year": 2020,
            "month_num": 3,
            "category": "Liquid Fund",
            "source_file": "amfi_2020_03.xls",
            "source_url": "https://example.com/amfi_2020_03.xls",
            "funds_mobilised_cr": 90000.0,
            "redemption_cr": 120000.0,
            "net_inflow_cr": -30000.0,
            "aum_cr": 435000.0,
            "avg_aum_cr": 450000.0,
        },
    ]
    pd.DataFrame(data).to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def populated_db(tmp_db: Path, sample_csv: Path) -> Path:
    """Return a temporary database pre-populated with sample_csv data."""
    import_csv(csv_path=sample_csv, db_path=tmp_db)
    return tmp_db


# ── 1. Database Initialization Tests ──────────────────────────────────────────

def test_init_db_creates_table_and_indexes(tmp_db: Path):
    """init_db should create the fund_flows_monthly table and required indexes."""
    assert not tmp_db.exists()
    init_db(tmp_db)
    assert tmp_db.exists()

    conn = get_connection(tmp_db)
    cur = conn.cursor()

    # Verify table existence
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (TABLE_NAME,)
    )
    assert cur.fetchone() is not None

    # Verify table column names
    cur.execute(f"PRAGMA table_info({TABLE_NAME})")
    cols = {row["name"] for row in cur.fetchall()}
    expected_cols = {
        "id", "month", "month_label", "month_year", "month_num", "category",
        "funds_mobilised_cr", "redemption_cr", "net_inflow_cr",
        "aum_cr", "avg_aum_cr", "source_file", "source_url", "created_at"
    }
    assert expected_cols.issubset(cols)

    # Verify indexes
    cur.execute(
        f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{TABLE_NAME}'"
    )
    indexes = {row["name"] for row in cur.fetchall()}
    assert "idx_fund_flows_cat_month" in indexes
    assert "idx_fund_flows_month" in indexes

    conn.close()


def test_init_db_is_idempotent(tmp_db: Path):
    """Running init_db multiple times on the same path must succeed cleanly."""
    init_db(tmp_db)
    init_db(tmp_db)
    init_db(tmp_db)
    assert tmp_db.exists()


# ── 2. CSV Import Tests ───────────────────────────────────────────────────────

def test_import_csv_sample(tmp_db: Path, sample_csv: Path):
    """import_csv should load all rows from sample CSV."""
    inserted = import_csv(csv_path=sample_csv, db_path=tmp_db)
    assert inserted == 5

    records = get_records(db_path=tmp_db)
    assert len(records) == 5
    assert records[0]["month"] == "2020-01"
    assert records[0]["category"] == "Liquid Fund"
    assert records[0]["net_inflow_cr"] == 10000.0


def test_import_csv_production_data_into_temp_db(tmp_db: Path):
    """Import the actual processed fund_flows_monthly.csv into a temporary database."""
    assert DEFAULT_CSV_PATH.exists(), "Processed CSV should exist from Phase 1"
    inserted = import_csv(csv_path=DEFAULT_CSV_PATH, db_path=tmp_db)
    assert inserted == 180

    summary = get_summary(db_path=tmp_db)
    assert summary["total_records"] == 180
    assert summary["start_month"] == "2019-04"
    assert summary["end_month"] == "2026-09"
    assert summary["distinct_months"] == 90
    assert set(summary["categories"]) == {"Liquid Fund", "Overnight Fund"}
    assert summary["category_counts"]["Liquid Fund"] == 90
    assert summary["category_counts"]["Overnight Fund"] == 90


# ── 3. Duplicate Prevention Tests ─────────────────────────────────────────────

def test_duplicate_prevention_on_repeated_import(tmp_db: Path, sample_csv: Path):
    """Re-importing the same CSV should not create duplicate rows."""
    first_insert = import_csv(csv_path=sample_csv, db_path=tmp_db)
    assert first_insert == 5

    second_insert = import_csv(csv_path=sample_csv, db_path=tmp_db)
    assert second_insert == 0

    third_insert = import_csv(csv_path=sample_csv, db_path=tmp_db)
    assert third_insert == 0

    records = get_records(db_path=tmp_db)
    assert len(records) == 5


def test_unique_constraint_enforced_by_sqlite(tmp_db: Path):
    """Direct duplicate INSERT must raise sqlite3.IntegrityError."""
    init_db(tmp_db)
    conn = get_connection(tmp_db)
    cur = conn.cursor()

    cur.execute(
        f"INSERT INTO {TABLE_NAME} (month, category) VALUES (?, ?)",
        ("2020-01", "Liquid Fund")
    )
    conn.commit()

    # Second insert with exact same month and category must fail
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            f"INSERT INTO {TABLE_NAME} (month, category) VALUES (?, ?)",
            ("2020-01", "Liquid Fund")
        )

    # Different category in same month must succeed
    cur.execute(
        f"INSERT INTO {TABLE_NAME} (month, category) VALUES (?, ?)",
        ("2020-01", "Overnight Fund")
    )
    conn.commit()

    conn.close()


# ── 4. Retrieval & Filtering Tests ────────────────────────────────────────────

def test_get_records_filter_by_category(populated_db: Path):
    """Retrieve records filtered by category, case-insensitively."""
    liquid = get_records(category="Liquid Fund", db_path=populated_db)
    assert len(liquid) == 3
    assert all(r["category"] == "Liquid Fund" for r in liquid)

    # Case-insensitive
    overnight = get_records(category="overnight fund", db_path=populated_db)
    assert len(overnight) == 2
    assert all(r["category"] == "Overnight Fund" for r in overnight)

    # Unknown category returns empty list
    equity = get_records(category="Equity Fund", db_path=populated_db)
    assert len(equity) == 0


def test_get_records_filter_by_date_range(populated_db: Path):
    """Filter records by start_month, end_month, or both."""
    # Start month
    from_feb = get_records(start_month="2020-02", db_path=populated_db)
    assert len(from_feb) == 3
    assert all(r["month"] >= "2020-02" for r in from_feb)

    # End month
    until_feb = get_records(end_month="2020-02", db_path=populated_db)
    assert len(until_feb) == 4
    assert all(r["month"] <= "2020-02" for r in until_feb)

    # Both
    feb_only = get_records(start_month="2020-02", end_month="2020-02", db_path=populated_db)
    assert len(feb_only) == 2
    assert {r["category"] for r in feb_only} == {"Liquid Fund", "Overnight Fund"}


def test_get_records_combined_filter(populated_db: Path):
    """Filter by both category and date range simultaneously."""
    res = get_records(
        category="Liquid Fund",
        start_month="2020-02",
        end_month="2020-03",
        db_path=populated_db,
    )
    assert len(res) == 2
    assert [r["month"] for r in res] == ["2020-02", "2020-03"]


def test_get_records_df(populated_db: Path):
    """get_records_df and as_dataframe=True should return a pandas DataFrame."""
    df1 = get_records(category="Liquid Fund", db_path=populated_db, as_dataframe=True)
    assert isinstance(df1, pd.DataFrame)
    assert len(df1) == 3
    assert "funds_mobilised_cr" in df1.columns

    df2 = get_records_df(category="Overnight Fund", db_path=populated_db)
    assert isinstance(df2, pd.DataFrame)
    assert len(df2) == 2


# ── 5. Summary Calculations Tests ─────────────────────────────────────────────

def test_get_summary_empty_database(tmp_db: Path):
    """get_summary on unpopulated database should return zeroed dict without error."""
    summary = get_summary(tmp_db)
    assert summary["total_records"] == 0
    assert summary["start_month"] is None
    assert summary["end_month"] is None
    assert summary["categories"] == []
    assert summary["category_counts"] == {}


def test_get_summary_populated(populated_db: Path):
    """get_summary should accurately compute counts, dates, and category metrics."""
    summary = get_summary(populated_db)
    assert summary["total_records"] == 5
    assert summary["start_month"] == "2020-01"
    assert summary["end_month"] == "2020-03"
    assert summary["distinct_months"] == 3
    assert set(summary["categories"]) == {"Liquid Fund", "Overnight Fund"}
    assert summary["category_counts"]["Liquid Fund"] == 3
    assert summary["category_counts"]["Overnight Fund"] == 2

    # Check by_category metrics
    liq = summary["by_category"]["Liquid Fund"]
    assert liq["count"] == 3
    assert liq["start_month"] == "2020-01"
    assert liq["end_month"] == "2020-03"
    # Total net inflow for Liquid = 10000 + 15000 - 30000 = -5000.0
    assert liq["total_net_inflow_cr"] == -5000.0


# ── 6. Error Handling Tests ───────────────────────────────────────────────────

def test_import_csv_missing_file_raises_error(tmp_db: Path):
    """Non-existent CSV file should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        import_csv(csv_path="non_existent.csv", db_path=tmp_db)


def test_import_csv_missing_columns_raises_error(tmp_db: Path, tmp_path: Path):
    """CSV missing required columns should raise DatabaseError."""
    bad_csv = tmp_path / "bad.csv"
    pd.DataFrame({"unrelated_col": [1, 2]}).to_csv(bad_csv, index=False)

    with pytest.raises(DatabaseError) as exc_info:
        import_csv(csv_path=bad_csv, db_path=tmp_db)
    assert "missing required columns" in str(exc_info.value)


def test_import_csv_aborts_without_partial_insert_on_missing_month(populated_db: Path, tmp_path: Path):
    """
    If a CSV contains rows with missing or blank 'month', the import must abort
    without writing partial data to the database.
    """
    count_before = len(get_records(db_path=populated_db))
    assert count_before == 5

    corrupted_csv = tmp_path / "corrupted_month.csv"
    data = [
        {
            "month": "2020-04",
            "month_label": "April 2020",
            "month_year": 2020,
            "month_num": 4,
            "category": "Liquid Fund",
            "source_file": "amfi_2020_04.xls",
            "source_url": "https://example.com/amfi_2020_04.xls",
            "funds_mobilised_cr": 100000.0,
            "redemption_cr": 90000.0,
            "net_inflow_cr": 10000.0,
            "aum_cr": 450000.0,
            "avg_aum_cr": 440000.0,
        },
        {
            "month": None,  # Corrupted row
            "month_label": "May 2020",
            "month_year": 2020,
            "month_num": 5,
            "category": "Liquid Fund",
            "source_file": "amfi_2020_05.xls",
            "source_url": "https://example.com/amfi_2020_05.xls",
            "funds_mobilised_cr": 100000.0,
            "redemption_cr": 90000.0,
            "net_inflow_cr": 10000.0,
            "aum_cr": 450000.0,
            "avg_aum_cr": 440000.0,
        },
    ]
    pd.DataFrame(data).to_csv(corrupted_csv, index=False)

    with pytest.raises(DatabaseError) as exc_info:
        import_csv(csv_path=corrupted_csv, db_path=populated_db)
    assert "missing or empty 'month'" in str(exc_info.value)

    # Ensure no partial rows were inserted
    count_after = len(get_records(db_path=populated_db))
    assert count_after == count_before


def test_import_csv_aborts_without_partial_insert_on_missing_category(populated_db: Path, tmp_path: Path):
    """
    If a CSV contains rows with missing or blank 'category', the import must abort
    without writing partial data to the database.
    """
    count_before = len(get_records(db_path=populated_db))
    assert count_before == 5

    corrupted_csv = tmp_path / "corrupted_cat.csv"
    data = [
        {
            "month": "2020-04",
            "month_label": "April 2020",
            "month_year": 2020,
            "month_num": 4,
            "category": "  ",  # Blank category
            "source_file": "amfi_2020_04.xls",
            "source_url": "https://example.com/amfi_2020_04.xls",
            "funds_mobilised_cr": 100000.0,
            "redemption_cr": 90000.0,
            "net_inflow_cr": 10000.0,
            "aum_cr": 450000.0,
            "avg_aum_cr": 440000.0,
        },
    ]
    pd.DataFrame(data).to_csv(corrupted_csv, index=False)

    with pytest.raises(DatabaseError) as exc_info:
        import_csv(csv_path=corrupted_csv, db_path=populated_db)
    assert "missing or empty 'category'" in str(exc_info.value)

    count_after = len(get_records(db_path=populated_db))
    assert count_after == count_before


def test_transaction_rollback_on_sqlite_exec_error(populated_db: Path, sample_csv: Path, monkeypatch):
    """
    If SQLite raises an error during executemany, the transaction context
    must roll back completely, leaving the database in its prior state.
    """
    count_before = len(get_records(db_path=populated_db))
    assert count_before == 5

    import app.data.db as db_mod
    orig_get_connection = db_mod.get_connection

    class CursorProxy:
        def __init__(self, real_cursor):
            self._cur = real_cursor

        def __getattr__(self, name):
            return getattr(self._cur, name)

        def executemany(self, *args, **kwargs):
            raise sqlite3.OperationalError("Simulated disk I/O failure mid-transaction")

    class ConnProxy:
        def __init__(self, real_conn):
            self._conn = real_conn

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def cursor(self, *args, **kwargs):
            return CursorProxy(self._conn.cursor(*args, **kwargs))

        def __enter__(self):
            return self._conn.__enter__()

        def __exit__(self, exc_type, exc_val, exc_tb):
            return self._conn.__exit__(exc_type, exc_val, exc_tb)

    def faulty_get_connection(db_path):
        conn = orig_get_connection(db_path)
        return ConnProxy(conn)

    monkeypatch.setattr(db_mod, "get_connection", faulty_get_connection)

    with pytest.raises(DatabaseError) as exc_info:
        import_csv(csv_path=sample_csv, db_path=populated_db)
    assert "CSV import failed" in str(exc_info.value)

    monkeypatch.undo()
    count_after = len(get_records(db_path=populated_db))
    assert count_after == count_before

