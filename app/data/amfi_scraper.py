"""
app/data/amfi_scraper.py
────────────────────────
Scrapes the AMFI Monthly report page, discovers all Excel download links
and returns a list of {label, url, fy_label} dicts.

Official source: https://www.amfiindia.com/research-information/amfi-monthly
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

AMFI_MONTHLY_URL = "https://www.amfiindia.com/research-information/amfi-monthly"
REQUEST_TIMEOUT = 30  # seconds
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# Months that the AMFI page labels in its accordion headings
MONTH_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{4})",
    re.IGNORECASE,
)


@dataclass
class ReportLink:
    """Metadata for one AMFI monthly Excel report."""

    month_label: str        # e.g. "April 2018"
    month_year: int         # e.g. 2018
    month_num: int          # 1-12
    fy_label: str           # e.g. "April 2018 - March 2019"
    url: str                # direct download URL
    file_type: str = "xlsx" # or "xls"


_MONTH_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_month_label(text: str) -> Optional[tuple[str, int, int]]:
    """Return (label, year, month_num) or None if not parseable."""
    m = MONTH_RE.search(text)
    if not m:
        return None
    month_name, year_str = m.group(1), m.group(2)
    return (
        f"{month_name.capitalize()} {year_str}",
        int(year_str),
        _MONTH_NUM[month_name.lower()],
    )


def fetch_report_links(
    start_year: int = 2018,
    start_month: int = 4,
) -> list[ReportLink]:
    """
    Scrape the AMFI Monthly page and return all Excel links for months
    >= (start_year, start_month).

    Returns an empty list — rather than raising — when the page is
    unreachable, logging the error for the caller.
    """
    try:
        resp = requests.get(AMFI_MONTHLY_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Cannot reach AMFI page: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    links: list[ReportLink] = []

    # AMFI page uses accordion panels; each panel heading contains a FY label
    # and each panel body contains month rows with Excel / PDF links.
    # Strategy: walk every <a> whose visible text is "Excel" (case-insensitive).

    current_fy = "Unknown"
    for tag in soup.find_all(True):
        # Try to capture FY accordion headings
        tag_text = tag.get_text(" ", strip=True)
        if re.search(r"april\s+\d{4}\s*[-–]\s*march\s+\d{4}", tag_text, re.IGNORECASE):
            current_fy = tag_text.strip()

        # Capture Excel links
        if tag.name == "a" and "excel" in tag.get_text(strip=True).lower():
            href = tag.get("href", "")
            if not href:
                continue
            if href.startswith("/"):
                href = "https://www.amfiindia.com" + href

            # Determine month label from surrounding context
            parent_text = ""
            for ancestor in tag.parents:
                ancestor_text = ancestor.get_text(" ", strip=True)
                parsed = _parse_month_label(ancestor_text)
                if parsed:
                    parent_text = ancestor_text
                    label, year, mnum = parsed
                    break
            else:
                logger.debug("Could not find month for link %s — skipped", href)
                continue

            # Filter by start date
            if (year, mnum) < (start_year, start_month):
                continue

            ext = "xls" if href.lower().endswith(".xls") else "xlsx"
            links.append(
                ReportLink(
                    month_label=label,
                    month_year=year,
                    month_num=mnum,
                    fy_label=current_fy,
                    url=href,
                    file_type=ext,
                )
            )

    # Deduplicate by (year, month) keeping the first occurrence
    seen: set[tuple[int, int]] = set()
    unique: list[ReportLink] = []
    for lnk in links:
        key = (lnk.month_year, lnk.month_num)
        if key not in seen:
            seen.add(key)
            unique.append(lnk)

    unique.sort(key=lambda x: (x.month_year, x.month_num))
    logger.info("Discovered %d unique monthly Excel links (>= %s/%s)", len(unique), start_month, start_year)
    return unique
