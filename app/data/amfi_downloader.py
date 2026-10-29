"""
app/data/amfi_downloader.py
────────────────────────────
Downloads AMFI monthly Excel files discovered by amfi_scraper.
Saves files to data/raw/amfi/ with deterministic filenames.
Records a source manifest so every row can be traced.
"""

from __future__ import annotations

import csv
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from app.data.amfi_scraper import ReportLink

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 60
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds between retries
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def _raw_dir(base_dir: Path) -> Path:
    p = base_dir / "data" / "raw" / "amfi"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _filename(link: ReportLink) -> str:
    """Deterministic local filename: amfi_YYYY_MM.xlsx / .xls"""
    return f"amfi_{link.month_year}_{link.month_num:02d}.{link.file_type}"


def download_report(
    link: ReportLink,
    base_dir: Path,
    skip_existing: bool = True,
) -> tuple[Optional[Path], bool]:
    """
    Download a single report.

    Returns:
        (path, was_downloaded) where:
          - path is the local Path on success, None on failure.
          - was_downloaded is True if a network request was attempted,
            False if the file was skipped (already existed).
    """
    dest = _raw_dir(base_dir) / _filename(link)
    if skip_existing and dest.exists() and dest.stat().st_size > 0:
        logger.info("Already exists, skipping: %s", dest.name)
        return dest, False   # skipped — no network request made

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(link.url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True)
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=65536):
                    fh.write(chunk)
            logger.info("Downloaded: %s -> %s (%d bytes)", link.month_label, dest.name, dest.stat().st_size)
            return dest, True
        except requests.RequestException as exc:
            logger.warning("Attempt %d/%d failed for %s: %s", attempt, RETRY_ATTEMPTS, link.month_label, exc)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY)

    logger.error("All retries failed for %s (%s)", link.month_label, link.url)
    return None, True   # was_downloaded=True (attempted but failed)


def download_all(
    links: list[ReportLink],
    base_dir: Path,
    skip_existing: bool = True,
    pause_between: float = 1.5,
) -> tuple[list[Path], list[ReportLink]]:
    """
    Download all reports.  Only pauses after actual network downloads;
    already-existing files are skipped instantly.
    Returns (successful_paths, failed_links).
    """
    successful: list[Path] = []
    failed: list[ReportLink] = []

    for i, link in enumerate(links, 1):
        logger.info("[%d/%d] %s", i, len(links), link.month_label)
        result, was_downloaded = download_report(link, base_dir, skip_existing=skip_existing)
        if result is not None:
            successful.append(result)
        else:
            failed.append(link)
        # Be polite to the AMFI server — only pause after real network activity
        if was_downloaded and i < len(links):
            time.sleep(pause_between)

    logger.info(
        "Download complete: %d succeeded, %d failed",
        len(successful), len(failed),
    )
    return successful, failed


def write_source_manifest(
    links: list[ReportLink],
    successful_paths: list[Path],
    base_dir: Path,
) -> Path:
    """
    Write a CSV manifest: month_label, fy_label, url, local_file, downloaded_at.
    """
    manifest_path = _raw_dir(base_dir) / "source_manifest.csv"
    successful_names = {p.name for p in successful_paths}
    now = datetime.now(timezone.utc).isoformat()

    with open(manifest_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["month_label", "month_year", "month_num", "fy_label",
                        "url", "local_file", "status", "downloaded_at"],
        )
        writer.writeheader()
        for lnk in links:
            fname = _filename(lnk)
            status = "ok" if fname in successful_names else "failed"
            writer.writerow({
                "month_label": lnk.month_label,
                "month_year": lnk.month_year,
                "month_num": lnk.month_num,
                "fy_label": lnk.fy_label,
                "url": lnk.url,
                "local_file": fname,
                "status": status,
                "downloaded_at": now if status == "ok" else "",
            })

    logger.info("Manifest written: %s (%d rows)", manifest_path.name, len(links))
    return manifest_path
