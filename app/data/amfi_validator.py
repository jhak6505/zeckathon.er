"""
app/data/amfi_validator.py
──────────────────────────
Validates the combined fund_flows_monthly.csv dataset and reports
issues without silently correcting them.
"""

from __future__ import annotations

import calendar
import logging
from typing import NamedTuple

import pandas as pd

logger = logging.getLogger(__name__)

EXPECTED_CATEGORIES = {"Liquid Fund", "Overnight Fund"}
# Overnight Fund launched in July 2019 (SEBI circular dated 6 Sep 2018,
# effective October 2018).  Before that month expect only Liquid Fund.
OVERNIGHT_START = (2018, 10)   # (year, month_num)


class ValidationReport(NamedTuple):
    missing_months: list[str]
    duplicate_records: pd.DataFrame
    missing_values: pd.DataFrame
    reconciliation_issues: list[str]
    category_issues: list[str]
    summary: str


def validate(df: pd.DataFrame) -> ValidationReport:
    """Run all validation checks and return a ValidationReport."""
    issues_recon: list[str] = []
    issues_cat:   list[str] = []

    # ── 1. Duplicate month-category records ───────────────────────────────────
    dupes = df[df.duplicated(subset=["month_year", "month_num", "category"], keep=False)]

    # ── 2. Missing values ─────────────────────────────────────────────────────
    value_cols = ["funds_mobilised_cr", "redemption_cr", "net_inflow_cr", "avg_aum_cr", "aum_cr"]
    missing_mask = df[value_cols].isnull().any(axis=1)
    missing_vals = df[missing_mask][["month_label", "category"] + value_cols]

    # ── 3. Missing months ─────────────────────────────────────────────────────
    missing_months = _check_missing_months(df, issues_cat)

    # ── 4. Reconciliation check ───────────────────────────────────────────────
    tol = 0.5
    for _, row in df.iterrows():
        m, r, n = row.get("funds_mobilised_cr"), row.get("redemption_cr"), row.get("net_inflow_cr")
        if all(v is not None and pd.notna(v) for v in (m, r, n)):
            expected = round(float(m) - float(r), 2)
            actual   = round(float(n), 2)
            if abs(expected - actual) > tol:
                issues_recon.append(
                    f"{row['month_label']} | {row['category']}: "
                    f"mobilised({m}) - redemption({r}) = {expected}, "
                    f"but net_inflow = {actual} (diff={round(actual-expected,2)} Cr)"
                )

    # ── 5. Summary ────────────────────────────────────────────────────────────
    lines = [
        f"Records:              {len(df)}",
        f"Duplicates:           {len(dupes)}",
        f"Rows with NaN values: {missing_mask.sum()}",
        f"Missing months:       {len(missing_months)}",
        f"Recon issues:         {len(issues_recon)}",
        f"Category issues:      {len(issues_cat)}",
    ]
    summary = "\n".join(lines)

    return ValidationReport(
        missing_months=missing_months,
        duplicate_records=dupes,
        missing_values=missing_vals,
        reconciliation_issues=issues_recon,
        category_issues=issues_cat,
        summary=summary,
    )


def _check_missing_months(df: pd.DataFrame, issues: list[str]) -> list[str]:
    """Return list of month strings where expected records are absent."""
    if df.empty:
        return []

    sorted_df = df.sort_values(["month_year", "month_num"]).reset_index(drop=True)
    min_y, min_m = int(sorted_df.iloc[0]["month_year"]), int(sorted_df.iloc[0]["month_num"])
    max_y, max_m = int(sorted_df.iloc[-1]["month_year"]), int(sorted_df.iloc[-1]["month_num"])

    present: set[tuple[int, int, str]] = {
        (int(r["month_year"]), int(r["month_num"]), r["category"])
        for _, r in df.iterrows()
    }

    missing: list[str] = []
    y, m = min_y, min_m
    while (y, m) <= (max_y, max_m):
        expected_cats = {"Liquid Fund"}
        if (y, m) >= OVERNIGHT_START:
            expected_cats.add("Overnight Fund")

        for cat in expected_cats:
            if (y, m, cat) not in present:
                month_name = calendar.month_abbr[m]
                missing.append(f"{month_name} {y} | {cat}")
                issues.append(f"Missing: {month_name} {y} | {cat}")

        m += 1
        if m > 12:
            m = 1
            y += 1

    return missing


def print_report(report: ValidationReport) -> None:
    """Pretty-print validation report to stdout/log."""
    separator = "─" * 60
    logger.info("\n%s\nVALIDATION REPORT\n%s", separator, separator)
    logger.info("Summary:\n%s", report.summary)

    if report.missing_months:
        logger.warning("Missing months (%d):", len(report.missing_months))
        for m in report.missing_months:
            logger.warning("  - %s", m)
    else:
        logger.info("No missing months detected.")

    if not report.duplicate_records.empty:
        logger.warning("Duplicate records:\n%s", report.duplicate_records.to_string())
    else:
        logger.info("No duplicate records.")

    if not report.missing_values.empty:
        logger.warning("Rows with missing values:\n%s", report.missing_values.to_string())
    else:
        logger.info("No missing values.")

    if report.reconciliation_issues:
        logger.warning("Reconciliation issues (%d):", len(report.reconciliation_issues))
        for issue in report.reconciliation_issues:
            logger.warning("  ! %s", issue)
    else:
        logger.info("No reconciliation issues.")

    if report.category_issues:
        logger.warning("Category/period issues (%d):", len(report.category_issues))
        for issue in report.category_issues:
            logger.warning("  ! %s", issue)
    logger.info(separator)

