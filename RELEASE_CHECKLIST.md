# FINHYPE — Hackathon Release Candidate Checklist

**Project:** FINHYPE — Quantitative Treasury Liquidity & Fund Flow Forecasting  
**Hackathon:** Zeckathon 2026 · Problem Statement 3  
**Verification Date:** 2026-10-29  
**Git Status:** Standalone directory (`fatal: not a git repository` — all changes preserved locally)  
**Acceptance Status:** **PASS — RELEASE CANDIDATE 1.0 CERTIFIED**  

---

## 1. Automated Quality & Integrity Gates

| Check Category | Acceptance Criterion | Verification Method | Status |
|:---|:---|:---|:---:|
| **Automated Test Suite** | 100% pass rate across all unit and integration suites | `pytest -v --tb=short` (154 tests in ~11.2s) | **PASS** |
| **Pipeline Execution** | End-to-end execution of all 7 pipeline stages without error | `python run_pipeline.py --skip-backtest` | **PASS** |
| **Data Continuity** | 90 continuous monthly records (Apr 2019 – Sep 2026) with zero nulls | Verified in `tests/test_data_integrity_audit.py` | **PASS** |
| **Accounting Invariance** | Net Inflow = Funds Mobilised − Repurchase (tolerance $\le 0.01\text{ Cr}$) | Verified across 180 historical AMFI records | **PASS** |
| **Database Constraints** | Unique `(month, category)` constraint prevents duplicate ingestion | Verified in `tests/test_db.py` | **PASS** |
| **Zero Temporal Leakage** | Features and scalers fitted strictly on $t \le T$; future data mutations invariant | Verified in `tests/test_audit_phase2.py` | **PASS** |
| **Interval Calibration** | Prediction intervals use only historical errors realized prior to origin | Verified in `tests/test_audit_phase2.py` | **PASS** |
| **Model-Quantile Parity** | Point forecasts and error quantiles strictly matched within model family | Verified in `tests/test_financial_calculation_audit.py` | **PASS** |
| **Cumulative Deficit Logic** | Multi-month peak deficit aggregation reproduces manual calculation | Verified in `tests/test_financial_calculation_audit.py` | **PASS** |
| **Dashboard Parity** | Dashboard calculations match production service across all 12 combinations | Verified in `tests/test_financial_calculation_audit.py` | **PASS** |

---

## 2. Release Artifacts Inventory

All required precomputed artifacts are present in `data/processed/`:

1. `data/finhype.db` (180 normalized records, SQLite)
2. `data/processed/fund_flows_monthly.csv` (180 rows, Apr 2019 – Sep 2026)
3. `data/processed/external_factors_monthly.csv` (90 rows, RBI Repo Rate & Nifty 50)
4. `data/processed/featured_fund_flows.csv` (180 rows, 53 engineered indicators)
5. `data/processed/backtest_results.csv` (576 evaluation rows, 24 origins)
6. `data/processed/backtest_metrics_summary.csv` (Audited comparative metrics table)
7. `data/processed/forward_forecasts_3m.csv` (24 forward configurations, Oct–Dec 2026)
8. `reports/figures/*.html` (6 standalone interactive Plotly visual artifacts)

---

## 3. Demonstration Commands Summary

### A. Windows PowerShell (Primary Demonstration Path)
```powershell
# Open terminal in project root C:\Users\Alok\Desktop\FINHYPE

# 1. Launch Interactive Dashboard (Fast startup, < 1.0s)
.\run.ps1 -OnlyDashboard

# 2. Run Full Pipeline Refresh + Launch Dashboard
.\run.ps1 -Dashboard

# 3. Execute Complete Automated Verification Suite
pytest -v --tb=short
```

### B. Windows Command Prompt (cmd.exe)
```cmd
REM Launch Dashboard
.\run.bat --only-dashboard

REM Run Pipeline + Launch Dashboard
.\run.bat --dashboard
```

### C. Standard Python CLI (Cross-Platform)
```bash
# Run pipeline using existing backtest cache (~19s)
python run_pipeline.py --skip-backtest

# Launch Streamlit dashboard directly
streamlit run app/dashboard.py
```

---

## 4. Key Treasury Figures Sign-Off (Origin: September 2026)

* **Liquid Funds (Current AUM: ₹625,847.01 Cr, Base Floor: 5.0% = ₹31,292.35 Cr)**:
  * 1-Month (Oct 2026): **₹31,292.35 Cr (5.00% of AUM)** [Floor-driven]
  * 3-Month Moderate (80%): **₹75,072.74 Cr (12.00% of AUM)** [Deficit-driven ahead of Dec tax drain]
  * 3-Month Conservative (95%): **₹106,161.75 Cr (16.96% of AUM)**
* **Overnight Funds (Current AUM: ₹84,032.57 Cr, Base Floor: 2.5% = ₹2,100.81 Cr)**:
  * 1-Month Standalone (Oct 2026, `SARIMAX` Top Model at 1M):
    * Moderate (80%): **₹10,366.04 Cr (12.34% of AUM)**
    * Conservative (95%): **₹17,606.86 Cr (20.95% of AUM)**
  * 3-Month Single-Model Baseline (`Seasonal-Naive` Persistence):
    * Moderate (80%): **₹74,130.35 Cr (88.22% of AUM)**
    * Conservative (95%): **₹118,049.89 Cr (140.48% of AUM)**
  * 3-Month Step-Wise Stitched Alternative (`SARIMAX` + `Seasonal-Naive` + `Seasonal-Naive`):
    * Moderate (80%): **₹90,640.30 Cr (107.86% of AUM)**
    * Conservative (95%): **₹129,620.28 Cr (154.25% of AUM)**

---

## 5. Live Demonstration Pre-Flight Checks

Before presenting to the judges:
* [x] Confirm Python virtual environment is activated (`.venv`).
* [x] Run `pytest -v --tb=short` to confirm all 154 tests pass.
* [x] Ensure port 8501 is not occupied by an older dangling process.
* [x] Launch dashboard with `.\run.ps1 -OnlyDashboard`.
* [x] Open browser to `http://localhost:8501` and verify Tab 1 through Tab 6 render with full interactivity.
* [x] Follow the 5-minute script outlined in `DEMO_GUIDE.md`.

