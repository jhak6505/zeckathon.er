"""
app/data/amfi_parser.py
────────────────────────
Parses a single AMFI monthly Excel file and extracts rows for
'Liquid Fund' and 'Overnight Fund' categories.

AMFI monthly Excel layouts:
  FORMAT A (Apr 2018 – Mar 2019): Binary XLS, sponsor-level aggregation only.
            Category-level data is NOT available in these files.
            Records the limitation as a warning, returns empty DataFrame.

  FORMAT B (Apr 2019 onwards):  XLSX (or modern binary XLS), category-level
            table starting from row ~2-3.  Columns include:
            Scheme Name/Category, Funds Mobilized, Repurchase/Redemption,
            Net Inflow/Outflow, Net Assets Under Management, Average Net Assets Under Management.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Target categories ─────────────────────────────────────────────────────────
TARGET_CATEGORIES = {"liquid fund", "overnight fund"}

CANONICAL_COLS = [
    "month",
    "month_label",
    "month_year",
    "month_num",
    "category",
    "funds_mobilised_cr",
    "redemption_cr",
    "net_inflow_cr",
    "aum_cr",
    "avg_aum_cr",
    "source_file",
    "source_url",
]

# Magic bytes for OOXML (xlsx)
_XLSX_MAGIC = b"PK"


def _is_xlsx(filepath: Path) -> bool:
    """Return True if the file is actually OOXML/XLSX regardless of extension."""
    return filepath.read_bytes()[:2] == _XLSX_MAGIC


# ── Format B header detection ─────────────────────────────────────────────────
_FORMAT_B_CATEGORY_KWORDS = ["scheme name", "scheme category", "fund category", "category", "categor"]
_FORMAT_B_FINANCIAL_KWORDS = ["mobiliz", "mobilis", "repurchase", "redemption", "inflow", "outflow"]


def _find_format_b_header_row(df_raw: pd.DataFrame) -> Optional[int]:
    """
    Find the row that has both a category/scheme keyword and a financial keyword.
    Returns the 0-based row index, or None.
    """
    for i, row in df_raw.iterrows():
        combined = " ".join(str(v).lower() for v in row.values)
        if any(k in combined for k in _FORMAT_B_FINANCIAL_KWORDS) and \
           any(k in combined for k in _FORMAT_B_CATEGORY_KWORDS):
            return i  # type: ignore[return-value]
    return None


def _normalise_header(raw: str) -> str:
    """Map a raw column header to a canonical name."""
    clean = str(raw).strip().lower()

    # Ignore segregated portfolio columns so they don't collide with main AUM
    if "segregated" in clean:
        return "segregated"

    # Specific AUM mappings (average vs closing)
    if "average" in clean or "aaum" in clean:
        return "avg_aum_cr"
    if "net assets under management" in clean or clean.startswith("aum as on") or clean == "aum":
        return "aum_cr"

    # Flow metrics
    if "net inflow" in clean or "net outflow" in clean or "net flow" in clean:
        return "net_inflow_cr"
    if "repurchase" in clean or "redemption" in clean:
        return "redemption_cr"
    if "mobiliz" in clean or "mobilis" in clean:
        return "funds_mobilised_cr"

    # Category / Scheme identifier
    if any(k in clean for k in ["scheme name", "scheme category", "fund category", "category"]):
        return "category"

    return clean


def _to_float(val: str) -> Optional[float]:
    """Convert string to float, return None for blanks / non-numeric."""
    val = str(val).strip().replace(",", "")
    if val in ("", "nan", "NaN", "None", "-", "--"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _check_reconciliation(df: pd.DataFrame, month_label: str, warnings: list[str]) -> None:
    """
    Warn if net_inflow_cr does not match (funds_mobilised_cr - redemption_cr)
    within a small tolerance (0.5 crore).
    """
    tol = 0.5
    for _, row in df.iterrows():
        inflow = row.get("funds_mobilised_cr")
        redeem = row.get("redemption_cr")
        net    = row.get("net_inflow_cr")
        if all(v is not None and pd.notna(v) for v in (inflow, redeem, net)):
            expected = round(float(inflow) - float(redeem), 2)
            actual   = round(float(net), 2)
            if abs(expected - actual) > tol:
                warnings.append(
                    f"{month_label} | {row['category']}: "
                    f"reconciliation mismatch — "
                    f"mobilised({inflow}) - redemption({redeem}) = {expected} "
                    f"but net_inflow = {actual} (diff={round(actual-expected,2)} Cr)"
                )


def parse_excel(
    filepath: Path,
    month_label: str,
    month_year: int,
    month_num: int,
    source_url: str,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Parse one AMFI monthly Excel file.

    Returns:
        df       – DataFrame with canonical columns, possibly empty.
        warnings – list of human-readable warning strings.
    """
    warnings: list[str] = []

    # ── 1. Determine engine ───────────────────────────────────────────────────
    xlsx = _is_xlsx(filepath)
    engine = "openpyxl" if xlsx else "xlrd"

    # ── 2. Load raw ───────────────────────────────────────────────────────────
    try:
        raw = pd.read_excel(filepath, sheet_name=0, header=None, dtype=str, engine=engine)
    except Exception as exc:
        warnings.append(f"{month_label}: cannot read file — {exc}")
        return pd.DataFrame(), warnings

    if raw.empty:
        warnings.append(f"{month_label}: Excel file is empty")
        return pd.DataFrame(), warnings

    # ── 3. Check for pre-April-2019 format (old sponsor-level XLS) ───────────
    if not xlsx:
        combined_text = " ".join(
            str(v).lower()
            for _, row in raw.iterrows()
            for v in row.values
        )
        if "sales - all schemes" in combined_text or "redemptions - all schemes" in combined_text:
            warnings.append(
                f"{month_label}: Format A (binary XLS, pre-April 2019) — "
                f"category-level Liquid/Overnight Fund data not available in this report. "
                f"AMFI switched to category-wise reporting from April 2019 onwards."
            )
            return pd.DataFrame(), warnings

    # ── 4. Locate header row (Format B) ───────────────────────────────────────
    hdr_idx = _find_format_b_header_row(raw)
    if hdr_idx is None:
        warnings.append(f"{month_label}: could not find header row in {filepath.name}")
        return pd.DataFrame(), warnings

    header_row = raw.iloc[hdr_idx]
    data = raw.iloc[hdr_idx + 1 :].copy().reset_index(drop=True)
    data.columns = [_normalise_header(str(h)) for h in header_row.values]

    # ── 5. Filter target categories ───────────────────────────────────────────
    cat_col = "category"
    if cat_col not in data.columns:
        warnings.append(f"{month_label}: 'category' column not found in {filepath.name}")
        return pd.DataFrame(), warnings

    data["_cat_norm"] = data[cat_col].astype(str).str.strip().str.lower().fillna("")
    subset = data[data["_cat_norm"].isin(TARGET_CATEGORIES)].copy()

    if subset.empty:
        warnings.append(f"{month_label}: no Liquid/Overnight Fund rows found in {filepath.name}")
        return pd.DataFrame(), warnings

    # ── 6. Build output ───────────────────────────────────────────────────────
    rows = []
    for _, row in subset.iterrows():
        rec: dict = {
            "month":              f"{month_year:04d}-{month_num:02d}",
            "month_label":        month_label,
            "month_year":         month_year,
            "month_num":          month_num,
            "category":           str(row[cat_col]).strip(),
            "source_file":        filepath.name,
            "source_url":         source_url,
        }
        for col in ["funds_mobilised_cr", "redemption_cr", "net_inflow_cr", "aum_cr", "avg_aum_cr"]:
            if col in row.index:
                val = _to_float(str(row[col]))
                rec[col] = val
            else:
                rec[col] = None
                warnings.append(f"{month_label}: column '{col}' missing in {filepath.name}")
        rows.append(rec)

    result = pd.DataFrame(rows)

    # ── 7. Reconciliation check ───────────────────────────────────────────────
    _check_reconciliation(result, month_label, warnings)

    return result, warnings
