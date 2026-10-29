"""
tests/test_amfi_scraper.py
──────────────────────────
Unit tests for app.data.amfi_scraper — all tests are offline
(no real HTTP calls are made).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.data.amfi_scraper import (
    _parse_month_label,
    _MONTH_NUM,
    fetch_report_links,
    ReportLink,
)


# ── _parse_month_label ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected_label,expected_year,expected_month", [
    ("April 2018",    "April 2018",    2018,  4),
    ("January 2024",  "January 2024",  2024,  1),
    ("december 2023", "December 2023", 2023, 12),
    ("Report for October 2020 period", "October 2020", 2020, 10),
])
def test_parse_month_label_valid(text, expected_label, expected_year, expected_month):
    result = _parse_month_label(text)
    assert result is not None
    label, year, mnum = result
    assert label == expected_label
    assert year  == expected_year
    assert mnum  == expected_month


@pytest.mark.parametrize("text", [
    "No month here",
    "2024",
    "April",
    "",
])
def test_parse_month_label_invalid(text):
    assert _parse_month_label(text) is None


# ── _MONTH_NUM completeness ───────────────────────────────────────────────────

def test_month_num_has_all_12_months():
    assert len(_MONTH_NUM) == 12
    assert set(_MONTH_NUM.values()) == set(range(1, 13))


# ── fetch_report_links — network failure ──────────────────────────────────────

def test_fetch_report_links_returns_empty_on_network_error():
    import requests as _req
    with patch("app.data.amfi_scraper.requests.get") as mock_get:
        mock_get.side_effect = _req.ConnectionError("Connection refused")
        result = fetch_report_links()
    assert result == []


def test_fetch_report_links_returns_empty_on_http_error():
    import requests as _req
    with patch("app.data.amfi_scraper.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = _req.HTTPError("404 Not Found")
        mock_get.return_value = mock_resp
        result = fetch_report_links()
    assert result == []


# ── fetch_report_links — HTML parsing ────────────────────────────────────────

_SAMPLE_HTML = """
<html><body>
  <h3>April 2024 - March 2025</h3>
  <table>
    <tr>
      <td>April 2024</td>
      <td><a href="/uploads/abc123.xlsx">Excel</a></td>
      <td><a href="/uploads/abc123.pdf">PDF</a></td>
    </tr>
    <tr>
      <td>May 2024</td>
      <td><a href="/uploads/def456.xlsx">Excel</a></td>
    </tr>
    <tr>
      <td>March 2018</td>
      <td><a href="/uploads/old.xlsx">Excel</a></td>
    </tr>
  </table>
</body></html>
"""


def test_fetch_report_links_parses_html():
    with patch("app.data.amfi_scraper.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = _SAMPLE_HTML
        mock_get.return_value = mock_resp

        # Start from April 2024 to exclude March 2018
        result = fetch_report_links(start_year=2024, start_month=4)

    assert len(result) == 2
    labels = [r.month_label for r in result]
    assert "April 2024" in labels
    assert "May 2024"   in labels


def test_fetch_report_links_filters_before_start():
    with patch("app.data.amfi_scraper.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = _SAMPLE_HTML
        mock_get.return_value = mock_resp

        result = fetch_report_links(start_year=2018, start_month=4)

    # March 2018 is before April 2018 — should be excluded
    labels = [r.month_label for r in result]
    assert "March 2018" not in labels


def test_fetch_report_links_deduplicates():
    """Duplicate Excel links for the same month should collapse to one."""
    html = """
    <html><body>
      <tr><td>April 2024</td><td><a href="/uploads/a.xlsx">Excel</a></td></tr>
      <tr><td>April 2024</td><td><a href="/uploads/b.xlsx">Excel</a></td></tr>
    </body></html>
    """
    with patch("app.data.amfi_scraper.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = html
        mock_get.return_value = mock_resp

        result = fetch_report_links(start_year=2024, start_month=4)

    april_links = [r for r in result if r.month_label == "April 2024"]
    assert len(april_links) == 1


def test_fetch_report_links_are_sorted():
    with patch("app.data.amfi_scraper.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = _SAMPLE_HTML
        mock_get.return_value = mock_resp

        result = fetch_report_links(start_year=2024, start_month=1)

    years_months = [(r.month_year, r.month_num) for r in result]
    assert years_months == sorted(years_months)


def test_report_link_url_prefix():
    """Relative URLs should be expanded to absolute."""
    with patch("app.data.amfi_scraper.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = _SAMPLE_HTML
        mock_get.return_value = mock_resp

        result = fetch_report_links(start_year=2024, start_month=4)

    for lnk in result:
        assert lnk.url.startswith("https://"), f"URL not absolute: {lnk.url}"
