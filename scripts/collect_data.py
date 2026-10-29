"""
scripts/collect_data.py
────────────────────────
Entry-point for Phase 1 data collection pipeline.

Usage (from the FINHYPE root):
    python scripts/collect_data.py [--start-year 2018] [--start-month 4] [--dry-run]

Steps:
  1. Scrape AMFI monthly page to discover Excel links.
  2. Download files to data/raw/amfi/.
  3. Parse each file, extract Liquid / Overnight Fund rows.
  4. Combine into data/processed/fund_flows_monthly.csv.
  5. Write source manifest to data/raw/amfi/source_manifest.csv.
  6. Validate dataset and print report.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Make sure project root is on the path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.data.amfi_scraper import fetch_report_links
from app.data.amfi_downloader import download_all, write_source_manifest
from app.data.amfi_parser import parse_excel
from app.data.amfi_validator import validate, print_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_CSV    = PROCESSED_DIR / "fund_flows_monthly.csv"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FINHYPE Phase 1 — Data Collection")
    p.add_argument("--start-year",  type=int, default=2018, help="Earliest year to collect (default: 2018)")
    p.add_argument("--start-month", type=int, default=4,    help="Earliest month to collect (default: 4 = April)")
    p.add_argument("--dry-run",     action="store_true",    help="Scrape links only; do not download or parse")
    p.add_argument("--no-skip",     action="store_true",    help="Re-download even if file already exists")
    return p


def main() -> None:
    args = build_parser().parse_args()

    # ── Step 1: Discover links ────────────────────────────────────────────────
    logger.info("═══ Step 1: Scraping AMFI monthly page ═══")
    links = fetch_report_links(start_year=args.start_year, start_month=args.start_month)

    manifest_path = ROOT / "data" / "raw" / "amfi" / "source_manifest.csv"
    if not links and manifest_path.exists():
        logger.warning(
            "Live AMFI page unreachable in current environment; reading discovered links from %s",
            manifest_path,
        )
        import csv
        with open(manifest_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for r in reader:
                y, m = int(r["month_year"]), int(r["month_num"])
                if (y, m) >= (args.start_year, args.start_month):
                    ext = "xls" if r["local_file"].endswith(".xls") else "xlsx"
                    from app.data.amfi_scraper import ReportLink
                    links.append(
                        ReportLink(
                            month_label=r["month_label"],
                            month_year=y,
                            month_num=m,
                            fy_label=r.get("fy_label", "Unknown"),
                            url=r["url"],
                            file_type=ext,
                        )
                    )

    if not links:
        logger.error(
            "No links discovered. The AMFI page may be unreachable in this environment.\n"
            "Manual alternative: visit https://www.amfiindia.com/research-information/amfi-monthly\n"
            "and download the Excel files into data/raw/amfi/ with names like amfi_YYYY_MM.xlsx"
        )
        sys.exit(1)

    logger.info("Discovered %d report links", len(links))
    for lnk in links:
        logger.info("  %s  ->  %s", lnk.month_label, lnk.url)

    if args.dry_run:
        logger.info("--dry-run: stopping after link discovery.")
        return

    # ── Step 2: Download ──────────────────────────────────────────────────────
    logger.info("\n═══ Step 2: Downloading reports ═══")
    successful_paths, failed_links = download_all(
        links, ROOT, skip_existing=not args.no_skip
    )
    if failed_links:
        logger.warning(
            "%d reports could not be downloaded:", len(failed_links)
        )
        for fl in failed_links:
            logger.warning("  FAILED: %s  (%s)", fl.month_label, fl.url)

    # Write source manifest regardless of failures
    write_source_manifest(links, successful_paths, ROOT)

    if not successful_paths:
        logger.error("No files downloaded. Cannot proceed to parsing.")
        sys.exit(1)

    # ── Step 3: Parse ─────────────────────────────────────────────────────────
    logger.info("\n═══ Step 3: Parsing Excel files ═══")
    all_records: list[pd.DataFrame] = []
    all_warnings: list[str] = []

    # Build a lookup from local filename -> link metadata
    link_by_file = {}
    for lnk in links:
        fname = f"amfi_{lnk.month_year}_{lnk.month_num:02d}.{lnk.file_type}"
        link_by_file[fname] = lnk

    for path in sorted(successful_paths):
        lnk = link_by_file.get(path.name)
        if lnk is None:
            logger.warning("No metadata for %s — skipping parse", path.name)
            continue

        df, warnings = parse_excel(
            filepath=path,
            month_label=lnk.month_label,
            month_year=lnk.month_year,
            month_num=lnk.month_num,
            source_url=lnk.url,
        )
        all_warnings.extend(warnings)
        if not df.empty:
            all_records.append(df)

    if all_warnings:
        logger.warning("\n═══ Parser warnings (%d) ═══", len(all_warnings))
        for w in all_warnings:
            logger.warning("  ⚠  %s", w)

    # ── Step 4: Combine & save ────────────────────────────────────────────────
    logger.info("\n═══ Step 4: Combining and saving ═══")
    if not all_records:
        logger.error("No records extracted — fund_flows_monthly.csv not written.")
        sys.exit(1)

    combined = pd.concat(all_records, ignore_index=True)
    combined = combined.sort_values(["month_year", "month_num", "category"]).reset_index(drop=True)

    # Ensure processed dir exists
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT_CSV, index=False)
    logger.info("Saved %d records to %s", len(combined), OUTPUT_CSV)

    # ── Step 5: Validate ──────────────────────────────────────────────────────
    logger.info("\n═══ Step 5: Validation ═══")
    report = validate(combined)
    print_report(report)

    # Exit with non-zero if critical issues
    has_issues = (
        len(report.duplicate_records) > 0
        or len(report.reconciliation_issues) > 0
    )
    sys.exit(1 if has_issues else 0)


if __name__ == "__main__":
    main()

