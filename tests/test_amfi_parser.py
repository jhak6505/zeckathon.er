"""
tests/test_amfi_parser.py
──────────────────────────
Unit tests for app.data.amfi_parser — uses synthetic Excel fixtures.
No real AMFI files are required.
"""

from __future__ import annotations

import io
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from app.data.amfi_parser import (
    _normalise_header,
    _find_format_b_header_row as _find_header_row,
    _to_float,
    parse_excel,
    TARGET_CATEGORIES,
)


# ── _to_float ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("123456.78", 123456.78),
    ("1,23,456.78", 123456.78),
    ("", None),
    ("-", None),
    ("nan", None),
    ("NaN", None),
    ("  123  ", 123.0),
    ("abc", None),
])
def test_to_float(raw, expected):
    assert _to_float(raw) == expected


# ── _normalise_header ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("Fund Category", "category"),
    ("Funds Mobilised (Cr)", "funds_mobilised_cr"),
    ("Funds Mobilized", "funds_mobilised_cr"),
    ("Repurchase / Redemption", "redemption_cr"),
    ("Net Inflow / Outflow (INR Crore)", "net_inflow_cr"),
    ("Average Net Assets Under Management", "avg_aum_cr"),
    ("Net Assets Under Management", "aum_cr"),
    ("AUM", "aum_cr"),
    ("Something Unknown", "something unknown"),   # passthrough
])
def test_normalise_header(raw, expected):
    assert _normalise_header(raw) == expected


# ── Fixtures: synthetic Excel file builders ───────────────────────────────────

def _make_excel_bytes(rows: list[list]) -> bytes:
    """Build an in-memory Excel file from a list-of-lists."""
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, header=False)
    buf.seek(0)
    return buf.read()


def _write_excel(tmp_path: Path, rows: list[list], fname: str = "test.xlsx") -> Path:
    p = tmp_path / fname
    p.write_bytes(_make_excel_bytes(rows))
    return p


# Canonical header row
_HEADER = [
    "Fund Category",
    "Funds Mobilised (Cr)",
    "Repurchase / Redemption",
    "Net Inflow / Outflow",
    "Average Net Assets Under Management",
    "Net Assets Under Management",
]


def _data_rows(category: str, mobilised: float, redemption: float, net: float,
               avg_aum: float, aum: float) -> list:
    return [category, mobilised, redemption, net, avg_aum, aum]


# ── _find_header_row ──────────────────────────────────────────────────────────

def test_find_header_row_at_zero():
    rows = [_HEADER, _data_rows("Liquid Fund", 100, 80, 20, 5000, 5100)]
    raw = pd.DataFrame(rows)
    assert _find_header_row(raw) == 0


def test_find_header_row_after_title_rows():
    rows = [
        ["AMFI Monthly Report", None, None, None, None, None],
        ["Period: April 2024",  None, None, None, None, None],
        _HEADER,
        _data_rows("Liquid Fund", 100, 80, 20, 5000, 5100),
    ]
    raw = pd.DataFrame(rows)
    assert _find_header_row(raw) == 2


def test_find_header_row_returns_none_when_missing():
    rows = [["A", "B", "C"], ["1", "2", "3"]]
    raw = pd.DataFrame(rows)
    assert _find_header_row(raw) is None


# ── parse_excel ───────────────────────────────────────────────────────────────

def test_parse_excel_extracts_liquid_fund(tmp_path):
    rows = [
        _HEADER,
        _data_rows("Liquid Fund",    500_000, 480_000, 20_000, 1_500_000, 1_520_000),
        _data_rows("Equity Fund",    100_000,  90_000, 10_000,   500_000,   510_000),
    ]
    path = _write_excel(tmp_path, rows)
    df, warns = parse_excel(path, "April 2024", 2024, 4, "https://example.com/test.xlsx")

    assert len(df) == 1
    assert df.iloc[0]["category"] == "Liquid Fund"
    assert df.iloc[0]["funds_mobilised_cr"] == 500_000.0
    assert df.iloc[0]["redemption_cr"]      == 480_000.0
    assert df.iloc[0]["net_inflow_cr"]      == 20_000.0
    assert df.iloc[0]["month_label"] == "April 2024"
    assert df.iloc[0]["month_year"]  == 2024
    assert df.iloc[0]["month_num"]   == 4


def test_parse_excel_extracts_both_fund_types(tmp_path):
    rows = [
        _HEADER,
        _data_rows("Liquid Fund",    500_000, 480_000, 20_000, 1_500_000, 1_520_000),
        _data_rows("Overnight Fund",  80_000,  75_000,  5_000,   300_000,   305_000),
        _data_rows("Debt Fund",       50_000,  48_000,  2_000,   200_000,   202_000),
    ]
    path = _write_excel(tmp_path, rows)
    df, warns = parse_excel(path, "October 2020", 2020, 10, "https://example.com/test.xlsx")

    assert len(df) == 2
    cats = set(df["category"].tolist())
    assert cats == {"Liquid Fund", "Overnight Fund"}


def test_parse_excel_no_target_category(tmp_path):
    rows = [
        _HEADER,
        _data_rows("Equity Fund", 100_000, 90_000, 10_000, 500_000, 510_000),
    ]
    path = _write_excel(tmp_path, rows)
    df, warns = parse_excel(path, "April 2024", 2024, 4, "https://example.com/test.xlsx")

    assert df.empty
    assert any("no Liquid/Overnight" in w for w in warns)


def test_parse_excel_reconciliation_mismatch_warns(tmp_path):
    # net != mobilised - redemption
    rows = [
        _HEADER,
        _data_rows("Liquid Fund", 500_000, 480_000, 15_000, 1_500_000, 1_520_000),
        #   expected net = 20_000, provided 15_000  => mismatch
    ]
    path = _write_excel(tmp_path, rows)
    df, warns = parse_excel(path, "April 2024", 2024, 4, "https://example.com/test.xlsx")

    assert len(df) == 1
    recon_warns = [w for w in warns if "reconciliation" in w]
    assert recon_warns, f"Expected reconciliation warning but got: {warns}"


def test_parse_excel_title_rows_before_header(tmp_path):
    rows = [
        ["AMFI Monthly Report — Industry Data", None, None, None, None, None],
        ["Period: April 2018",                  None, None, None, None, None],
        _HEADER,
        _data_rows("Liquid Fund", 100_000, 90_000, 10_000, 500_000, 510_000),
    ]
    path = _write_excel(tmp_path, rows)
    df, warns = parse_excel(path, "April 2018", 2018, 4, "https://example.com/test.xlsx")

    assert len(df) == 1
    assert df.iloc[0]["category"] == "Liquid Fund"


def test_parse_excel_empty_file_warns(tmp_path):
    rows: list[list] = []
    path = _write_excel(tmp_path, rows)
    df, warns = parse_excel(path, "April 2024", 2024, 4, "https://example.com/test.xlsx")

    assert df.empty
    assert warns  # some warning about empty or missing header


def test_parse_excel_source_metadata(tmp_path):
    rows = [_HEADER, _data_rows("Liquid Fund", 500, 400, 100, 5000, 5100)]
    path = _write_excel(tmp_path, rows)
    url  = "https://www.amfiindia.com/uploads/test123.xlsx"
    df, _ = parse_excel(path, "June 2022", 2022, 6, url)

    assert df.iloc[0]["source_url"]  == url
    assert df.iloc[0]["source_file"] == path.name


# ── TARGET_CATEGORIES constant ────────────────────────────────────────────────

def test_target_categories_constant():
    assert "liquid fund" in TARGET_CATEGORIES
    assert "overnight fund" in TARGET_CATEGORIES

