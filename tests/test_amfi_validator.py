"""
tests/test_amfi_validator.py
─────────────────────────────
Unit tests for app.data.amfi_validator.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.data.amfi_validator import validate, OVERNIGHT_START


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row(year: int, month: int, cat: str,
         mobilised=100.0, redemption=80.0, net=20.0,
         avg_aum=5000.0, aum=5100.0):
    return {
        "month_label":       f"{_mname(month)} {year}",
        "month_year":         year,
        "month_num":          month,
        "category":           cat,
        "funds_mobilised_cr": mobilised,
        "redemption_cr":      redemption,
        "net_inflow_cr":      net,
        "avg_aum_cr":         avg_aum,
        "aum_cr":             aum,
        "source_file":        "test.xlsx",
        "source_url":         "https://example.com",
    }


def _mname(m: int) -> str:
    import calendar
    return calendar.month_abbr[m]


def _df(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ── No issues ─────────────────────────────────────────────────────────────────

def test_validate_clean_dataset():
    # Only Liquid Fund rows (pre-Oct-2018 so no Overnight expected)
    df = _df(
        _row(2018, 4, "Liquid Fund"),
        _row(2018, 5, "Liquid Fund"),
        _row(2018, 6, "Liquid Fund"),
    )
    report = validate(df)
    assert len(report.duplicate_records) == 0
    assert len(report.reconciliation_issues) == 0
    assert report.missing_values.empty


# ── Duplicates ────────────────────────────────────────────────────────────────

def test_validate_detects_duplicates():
    df = _df(
        _row(2022, 1, "Liquid Fund"),
        _row(2022, 1, "Liquid Fund"),   # duplicate
    )
    report = validate(df)
    assert len(report.duplicate_records) == 2  # both rows flagged


def test_validate_no_false_duplicate_for_two_categories():
    df = _df(
        _row(2022, 1, "Liquid Fund"),
        _row(2022, 1, "Overnight Fund"),  # different category — not a dup
    )
    report = validate(df)
    assert len(report.duplicate_records) == 0


# ── Reconciliation ────────────────────────────────────────────────────────────

def test_validate_detects_reconciliation_mismatch():
    # net should be 100-80=20, but we supply 15
    df = _df(_row(2022, 3, "Liquid Fund", mobilised=100, redemption=80, net=15))
    report = validate(df)
    assert len(report.reconciliation_issues) == 1


def test_validate_no_recon_issue_within_tolerance():
    # Difference of 0.3 Cr — within 0.5 Cr tolerance
    df = _df(_row(2022, 3, "Liquid Fund", mobilised=100, redemption=80, net=20.3))
    report = validate(df)
    assert len(report.reconciliation_issues) == 0


def test_validate_recon_skipped_when_null():
    # If net is None, reconciliation should be skipped gracefully
    row = _row(2022, 3, "Liquid Fund")
    row["net_inflow_cr"] = None
    df = pd.DataFrame([row])
    report = validate(df)
    assert len(report.reconciliation_issues) == 0


# ── Missing values ────────────────────────────────────────────────────────────

def test_validate_detects_missing_values():
    row = _row(2022, 3, "Liquid Fund")
    row["aum_cr"] = None
    df = pd.DataFrame([row])
    report = validate(df)
    assert not report.missing_values.empty


def test_validate_no_missing_values_clean():
    df = _df(_row(2022, 3, "Liquid Fund"))
    report = validate(df)
    assert report.missing_values.empty


# ── Missing months ────────────────────────────────────────────────────────────

def test_validate_detects_missing_month():
    # April and June present, May is absent
    df = _df(
        _row(2018, 4, "Liquid Fund"),
        _row(2018, 6, "Liquid Fund"),
    )
    report = validate(df)
    assert any("May" in m and "2018" in m for m in report.missing_months)


def test_validate_no_missing_months_consecutive():
    df = _df(
        _row(2018, 4, "Liquid Fund"),
        _row(2018, 5, "Liquid Fund"),
        _row(2018, 6, "Liquid Fund"),
    )
    report = validate(df)
    assert len(report.missing_months) == 0


def test_validate_overnight_not_expected_before_start():
    # Before OVERNIGHT_START, Overnight Fund should not be expected
    oy, om = OVERNIGHT_START
    # One month before OVERNIGHT_START
    bm = om - 1 if om > 1 else 12
    by = oy if om > 1 else oy - 1
    df = _df(_row(by, bm, "Liquid Fund"))
    report = validate(df)
    # None of the missing months should mention Overnight Fund
    overnight_missing = [m for m in report.missing_months if "Overnight" in m]
    assert len(overnight_missing) == 0


# ── Summary string ────────────────────────────────────────────────────────────

def test_validate_summary_is_string():
    df = _df(_row(2022, 1, "Liquid Fund"))
    report = validate(df)
    assert isinstance(report.summary, str)
    assert "Records" in report.summary

