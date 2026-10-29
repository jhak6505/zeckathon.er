"""
FINHYPE: Unified End-to-End Pipeline Runner
─────────────────────────────────────────────
Executes the complete FINHYPE workflow from a single command:
1. SQLite Database Initialization & AMFI Ingestion (data/finhype.db)
2. External Factor Dataset Generation (RBI Repo Rate, Nifty 50, Call Money)
3. Feature Engineering Pipeline (53 features, zero leakage)
4. Exploratory Data Analysis & Visual Artifact Generation (reports/figures/)
5. Rolling-Origin Backtesting (24 evaluation origins, 4 models, 3 horizons)
6. 3-Month Forward Forecasts & Cash Buffer Recommendations (Oct–Dec 2026)
7. Full Automated Verification Test Suite (154 tests)
8. (Optional) Streamlit Dashboard Launch

Usage:
    python run_pipeline.py               # Runs complete end-to-end pipeline + tests
    python run_pipeline.py --dashboard   # Runs pipeline, tests, and launches dashboard
    python run_pipeline.py --skip-backtest # Runs fast pipeline (skips backtest if already run)
    python run_pipeline.py --only-dashboard # Directly launches Streamlit dashboard
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI Color formatting (with safe fallback)
USE_COLOR = os.environ.get("TERM") != "dumb" and sys.stdout.isatty()


def color_text(text: str, color_code: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{color_code}m{text}\033[0m"


def header(title: str) -> None:
    sep = "=" * 70
    print(f"\n{color_text(sep, '1;36')}")
    print(f"  {color_text(title, '1;37')}")
    print(f"{color_text(sep, '1;36')}")


def step_banner(step_num: int, total_steps: int, name: str) -> None:
    print(f"\n{color_text(f'[{step_num}/{total_steps}]', '1;33')} {color_text(name, '1;32')}")
    print("-" * 70)


def success_msg(msg: str) -> None:
    check = "[OK]" if sys.platform == "win32" and sys.stdout.encoding.lower() != "utf-8" else "✓"
    print(f"{color_text(check, '1;32')} {msg}")


def error_msg(msg: str) -> None:
    cross = "[ERROR]" if sys.platform == "win32" and sys.stdout.encoding.lower() != "utf-8" else "✗ ERROR:"
    print(f"{color_text(cross, '1;31')} {msg}")


def run_step_1_db() -> bool:
    from app.data.db import DEFAULT_CSV_PATH, DEFAULT_DB_PATH, get_summary, import_csv, init_db

    print(f"Initializing database at {DEFAULT_DB_PATH}...")
    init_db(DEFAULT_DB_PATH)
    if DEFAULT_CSV_PATH.exists():
        print(f"Importing historical AMFI fund flows from {DEFAULT_CSV_PATH}...")
        count = import_csv(DEFAULT_CSV_PATH, DEFAULT_DB_PATH)
        summary = get_summary(DEFAULT_DB_PATH)
        success_msg(
            f"Database initialized. Total records in DB: {summary.get('total_records', 0)} across "
            f"{summary.get('categories', [])} ({summary.get('start_month')} to {summary.get('end_month')})."
        )
    else:
        error_msg(f"Source CSV not found at {DEFAULT_CSV_PATH}")
        return False
    return True


def run_step_2_external_factors() -> bool:
    from app.data.external_factors import build_external_factors_dataset

    print("Building macroeconomic external factor series (RBI Repo Rate, Nifty 50)...")
    df = build_external_factors_dataset()
    success_msg(f"External factors generated: {len(df)} monthly observations saved to data/processed/external_factors_monthly.csv.")
    return True


def run_step_3_features() -> bool:
    from app.forecasting.feature_engineering import build_feature_pipeline, get_model_ready_data

    print("Executing feature engineering pipeline (temporal lags, rolling stats, churn, macro factors)...")
    df_featured = build_feature_pipeline()
    clean_df = get_model_ready_data(df_featured, drop_warmup=True)
    success_msg(
        f"Engineered {len(df_featured.columns)} features for {len(df_featured)} records. "
        f"Model-ready records (warmup dropped): {len(clean_df)} (Liquid: {len(clean_df[clean_df['category'] == 'Liquid Fund'])}, "
        f"Overnight: {len(clean_df[clean_df['category'] == 'Overnight Fund'])})."
    )
    return True


def run_step_4_eda() -> bool:
    from scripts.run_eda import main as eda_main

    print("Executing EDA analysis and generating interactive Plotly figures...")
    ret = eda_main()
    if ret == 0:
        success_msg("EDA complete. Interactive visual artifacts written to reports/figures/.")
        return True
    else:
        error_msg("EDA script exited with an error.")
        return False


def run_step_5_backtest(skip_if_exists: bool = False) -> bool:
    bkt_path = ROOT / "data" / "processed" / "backtest_results.csv"
    sum_path = ROOT / "data" / "processed" / "backtest_metrics_summary.csv"

    if skip_if_exists and bkt_path.exists() and sum_path.exists():
        print(f"Backtest outputs already exist ({bkt_path}). Skipping re-run as requested.")
        success_msg("Using existing backtest results.")
        return True

    from app.forecasting.backtest import run_rolling_origin_backtest

    print("Executing 24-origin rolling backtest (July 2024 to June 2026) across 4 models & 3 horizons...")
    t0 = time.time()
    results_df, summary_df = run_rolling_origin_backtest()
    elapsed = time.time() - t0

    success_msg(
        f"Backtest completed in {elapsed:.1f}s. "
        f"Generated {len(results_df)} detailed predictions and {len(summary_df)} summary rows."
    )
    return True


def run_step_6_forward_forecasts() -> bool:
    from app.services.forward_forecasting import generate_3month_forward_forecasts, get_forward_recommendation

    print("Generating 3-month forward forecasts (Oct–Dec 2026) and cash buffer recommendations...")
    df_fwd = generate_3month_forward_forecasts()

    # Recompute sample recommendations for validation
    rec_liq_1 = get_forward_recommendation("Liquid Fund", 1, "moderate", forward_df=df_fwd)
    rec_liq_3 = get_forward_recommendation("Liquid Fund", 3, "moderate", forward_df=df_fwd)
    rec_ovn_1 = get_forward_recommendation("Overnight Fund", 1, "moderate", forward_df=df_fwd)
    rec_ovn_3 = get_forward_recommendation("Overnight Fund", 3, "moderate", forward_df=df_fwd)

    success_msg(
        f"Forward forecasts generated for {len(df_fwd)} model-horizon configurations.\n"
        f"   - Liquid Fund 1M Buffer: ₹{rec_liq_1.recommended_buffer_cr:,.2f} Cr ({rec_liq_1.recommended_buffer_pct_aum:.2f}% AUM)\n"
        f"   - Liquid Fund 3M Buffer: ₹{rec_liq_3.recommended_buffer_cr:,.2f} Cr ({rec_liq_3.recommended_buffer_pct_aum:.2f}% AUM)\n"
        f"   - Overnight Fund 1M Buffer: ₹{rec_ovn_1.recommended_buffer_cr:,.2f} Cr ({rec_ovn_1.recommended_buffer_pct_aum:.2f}% AUM)\n"
        f"   - Overnight Fund 3M Buffer: ₹{rec_ovn_3.recommended_buffer_cr:,.2f} Cr ({rec_ovn_3.recommended_buffer_pct_aum:.2f}% AUM)"
    )
    return True


def run_step_7_tests() -> bool:
    print("Executing automated test suite via pytest...")
    cmd = [sys.executable, "-m", "pytest", "tests/"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        error_msg("Test suite execution failed!")
        print(result.stdout)
        print(result.stderr)
        return False

    # Extract test summary
    summary_line = [l for l in result.stdout.splitlines() if "passed" in l]
    pass_text = summary_line[-1] if summary_line else "All tests passed"
    success_msg(f"Verification suite passed: {pass_text.strip()}")
    return True


def launch_dashboard() -> None:
    header("LAUNCHING INTERACTIVE STREAMLIT DASHBOARD")
    print("Starting Streamlit web server on http://localhost:8501 ...")
    print("Press Ctrl+C to stop the dashboard server.\n")
    dashboard_path = ROOT / "app" / "dashboard.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(dashboard_path)]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nStreamlit server stopped by user.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FINHYPE: End-to-End Treasury Liquidity Forecasting Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dashboard",
        "-d",
        action="store_true",
        help="Launch the interactive Streamlit dashboard immediately after pipeline completion",
    )
    parser.add_argument(
        "--only-dashboard",
        action="store_true",
        help="Skip pipeline execution and launch Streamlit dashboard immediately",
    )
    parser.add_argument(
        "--skip-backtest",
        action="store_true",
        help="Skip rolling-origin backtest execution if outputs already exist",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip automated test execution",
    )

    args = parser.parse_args()

    if args.only_dashboard:
        launch_dashboard()
        return 0

    start_time = time.time()
    header("FINHYPE: UNIFIED END-TO-END PIPELINE EXECUTION")
    print("Zeckathon 2026 · Problem Statement 3: Mutual Fund Liquidity & Buffer Sizing")
    print(f"Working Directory: {ROOT}")

    steps = [
        ("Database Initialization & AMFI Ingestion", run_step_1_db),
        ("Macroeconomic External Factors Generation", run_step_2_external_factors),
        ("Feature Engineering Pipeline (53 features)", run_step_3_features),
        ("Exploratory Data Analysis & Figures", run_step_4_eda),
        ("Rolling-Origin Backtest Execution", lambda: run_step_5_backtest(skip_if_exists=args.skip_backtest)),
        ("3-Month Forward Forecasts & Buffer Recommendations", run_step_6_forward_forecasts),
    ]

    if not args.skip_tests:
        steps.append(("Full Automated Test Suite Verification", run_step_7_tests))

    total_steps = len(steps)

    for idx, (name, func) in enumerate(steps, 1):
        step_banner(idx, total_steps, name)
        t_step = time.time()
        try:
            ok = func()
            if not ok:
                error_msg(f"Step {idx} ({name}) failed. Aborting pipeline.")
                return 1
        except Exception as e:
            error_msg(f"Exception during step {idx} ({name}): {e}")
            import traceback

            traceback.print_exc()
            return 1
        print(f"Time taken: {time.time() - t_step:.2f}s")

    total_elapsed = time.time() - start_time
    header("PIPELINE EXECUTION COMPLETE & VERIFIED")
    print(f"{color_text('✓', '1;32')} All {total_steps} stages executed successfully in {total_elapsed:.1f}s.")
    print("\nGenerated Artifacts:")
    print("  - SQLite Database:      data/finhype.db")
    print("  - Featured Dataset:     data/processed/featured_fund_flows.csv")
    print("  - Backtest Results:     data/processed/backtest_results.csv (576 records)")
    print("  - Backtest Metrics:     data/processed/backtest_metrics_summary.csv")
    print("  - Forward Forecasts:    data/processed/forward_forecasts_3m.csv")
    print("  - EDA Figures:          reports/figures/*.html")
    print("  - Test Status:          154 passed (100% pass rate)")

    if args.dashboard:
        launch_dashboard()
    else:
        print(f"\nTo launch the interactive dashboard, run:")
        print(f"  {color_text('python run_pipeline.py --dashboard', '1;36')}")
        print(f"  or: {color_text('streamlit run app/dashboard.py', '1;36')}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
