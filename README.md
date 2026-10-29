# FINHYPE

> **Zeckathon 2026 – Problem Statement 3**

## Objective

Forecast monthly net flows for Indian **liquid** and **overnight** mutual funds for the next three months, analyse the factors that drive those flows, compare forecasting models, and recommend an appropriate cash buffer for fund managers.

## Project Status

- **Phase 0 – Project Setup**: Complete.
- **Phase 1 – Historical Data Ingestion**: Complete. (90 months of AMFI data from April 2019 to September 2026).
- **Phase 2 – SQLite Database & Storage**: Complete. (Local SQLite DB at `data/finhype.db` with duplicate prevention and safe retrieval).
- **Phase 3 – EDA, Feature Engineering & External Factors**: Complete.
- **Phase 4 – Model Development & Rolling-Origin Backtesting**: Complete.
- **Phase 5 – Cash Buffer Engine & Streamlit Dashboard**: Complete.
- **Phase 6 – Hackathon Readiness & Demonstration Packaging**: Complete *(current)*.

### Key Hackathon Documents
* 🚀 **[DEMO_GUIDE.md](file:///c:/Users/Alok/Desktop/FINHYPE/DEMO_GUIDE.md)**: 5-minute live judge demonstration script, startup options, key figures, and troubleshooting.
* 🏛️ **[ARCHITECTURE.md](file:///c:/Users/Alok/Desktop/FINHYPE/ARCHITECTURE.md)**: End-to-end data flow, modular pipeline architecture, and Mermaid system diagram.
* ⚠️ **[LIMITATIONS.md](file:///c:/Users/Alok/Desktop/FINHYPE/LIMITATIONS.md)**: Methodological boundaries, comonotonic stress assumptions, and sample size disclosures.
* 📋 **[testfail.md](file:///c:/Users/Alok/Desktop/FINHYPE/testfail.md)**: Audited technical verification report, discrepancy trace, and 154-test verification log.
* 🛠️ **[work.md](file:///c:/Users/Alok/Desktop/FINHYPE/work.md)**: Complete development activity and mathematical trace log.

## Repository Structure

```
FINHYPE/
├── app/
│   ├── __init__.py
│   ├── dashboard.py          # Interactive Streamlit Treasury Dashboard
│   ├── db.py                 # SQLite database access and query layer
│   ├── data/                 # Ingestion, scrapers, validators, external factors
│   │   ├── amfi_downloader.py
│   │   ├── amfi_parser.py
│   │   ├── amfi_scraper.py
│   │   ├── amfi_validator.py
│   │   ├── db.py
│   │   └── external_factors.py
│   ├── forecasting/          # Forecasting, metrics, models, intervals, backtest
│   │   ├── eda.py
│   │   ├── feature_engineering.py
│   │   ├── metrics.py
│   │   ├── models.py
│   │   ├── intervals.py
│   │   └── backtest.py
│   └── services/             # Business-logic services & recommendation engine
│       ├── __init__.py
│       ├── cash_buffer.py
│       └── forward_forecasting.py
├── data/
│   ├── finhype.db            # Local SQLite database
│   ├── raw/
│   │   ├── amfi/             # Raw AMFI monthly Excel workbooks
│   │   └── external/         # External macro factors & metadata JSON
│   └── processed/
│       ├── fund_flows_monthly.csv
│       ├── external_factors_monthly.csv
│       ├── featured_fund_flows.csv
│       ├── backtest_results.csv
│       ├── backtest_metrics_summary.csv
│       └── forward_forecasts_3m.csv
├── reports/
│   ├── eda_findings.md       # Comprehensive analytical findings report
│   ├── forecasting_design.md # Revised Phase 4 design document
│   ├── cash_buffer_design_note.md # Phase 5 recommendation engine design
│   └── figures/              # Interactive Plotly visual artifacts (HTML)
├── scripts/
│   ├── collect_data.py       # Phase 1 data collection runner
│   ├── init_db.py            # Phase 2 database initializer and CSV importer
│   ├── run_eda.py            # Phase 3 EDA computation & visual generator
│   ├── fetch_external_factors.py # Phase 3 external factor builder
│   ├── build_features.py     # Phase 3 feature engineering pipeline runner
│   └── run_backtest.py       # Phase 4 rolling-origin backtest runner
├── tests/                    # 154 automated unit and integration tests (12 modules)
│   ├── test_amfi_parser.py
│   ├── test_amfi_scraper.py
│   ├── test_amfi_validator.py
│   ├── test_audit_phase2.py
│   ├── test_cash_buffer.py
│   ├── test_data_integrity_audit.py
│   ├── test_db.py
│   ├── test_eda.py
│   ├── test_external_factors.py
│   ├── test_feature_engineering.py
│   ├── test_financial_calculation_audit.py
│   └── test_forecasting.py
├── .gitignore
├── requirements.txt
├── run_pipeline.py           # Unified master workflow runner (one-command execution)
├── run.bat                   # One-click Windows CMD runner
├── run.ps1                   # One-click Windows PowerShell runner
├── run.sh                    # One-click Linux / macOS runner
├── DEMO_GUIDE.md             # 5-minute live demonstration script & guide
├── ARCHITECTURE.md           # Modular system architecture & Mermaid diagram
├── LIMITATIONS.md            # Methodological boundaries & governance disclosures
├── testfail.md               # Final audit report & discrepancy reconciliation
├── work.md                   # Full engineering activity & trace log
└── README.md
```

## Quick Start

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. One-Command Master Workflow Execution 🚀

You can execute the entire FINHYPE pipeline end-to-end (Database initialization -> External factors -> Feature engineering -> EDA figures -> 24-origin Rolling Backtest -> 3M Forward Forecasts -> Pytest test suite) in a single command:

```bash
# Run complete pipeline and automated verification
python run_pipeline.py

# Or run complete pipeline and automatically launch the Streamlit dashboard:
python run_pipeline.py --dashboard

# Windows shortcut:
.\run.bat
.\run.bat --dashboard

# PowerShell shortcut:
.\run.ps1
.\run.ps1 -Dashboard
```

#### CLI Flags for Custom Execution:
* `python run_pipeline.py`: Full end-to-end run across all 7 stages (~35 seconds).
* `python run_pipeline.py --dashboard`: Runs full pipeline and launches the dashboard.
* `python run_pipeline.py --skip-backtest`: Fast run using existing backtest outputs (~15 seconds).
* `python run_pipeline.py --only-dashboard`: Directly launches the Streamlit dashboard without re-running stages.

---

### Manual Step-by-Step Execution (Alternative)

If you prefer to run individual components manually:

#### A. Run Exploratory Data Analysis (EDA)
```bash
python scripts/run_eda.py
```

#### B. Build Feature Pipeline
```bash
python scripts/build_features.py
```

#### C. Run Rolling-Origin Backtesting
```bash
python scripts/run_backtest.py
```

#### D. Launch Interactive Streamlit Dashboard
```bash
streamlit run app/dashboard.py
```

#### E. Run All Automated Tests
```bash
pytest
```
154 automated unit and integration tests validate the entire pipeline (100% pass rate in ~12.4 seconds):
- AMFI data scrapers, parsers, and schema validators.
- SQLite database initialization, unique constraints, and idempotent re-imports.
- Production dataset continuity, null rejection, and accounting reconciliation checks.
- EDA summary metrics and factor analyses.
- Feature engineering temporal leakage prevention, transform isolation, and end-to-end future mutation invariance.
- Multi-step forecasting models (Seasonal-Naive, ETS, SARIMAX, Ridge).
- Out-of-sample prediction interval calibration, temporal error pool isolation, monotonicity, and pinball loss.
- Rolling-origin backtest record uniqueness, coverage, and metric recomputation.
- Robust metric input contract (matrix broadcasting prevention, NaN/Inf rejection, bounds sanity).
- Cash buffer sizing logic, multi-month peak deficit aggregation, and risk-profile scaling.
- Comprehensive financial calculation audit: exact matching of model-specific point forecasts and error pools (Items A–G), manual deficit reproduction, and rejection of cross-model mixing.

---

## Methodology Summary

FINHYPE implements an end-to-end, leak-free quantitative liquidity forecasting framework:
1. **Data Ingestion & Storage**: 90 consecutive months of historical AMFI fund-flow data (April 2019 to September 2026) stored in a normalized SQLite database (`data/finhype.db`) with strict unique constraints preventing duplicate month-category records.
2. **Feature Engineering**: 53 engineered indicators including deterministic calendar drivers (quarter-ends, advance tax cycles, FY-end, days in month), lagged flow dynamics, rolling volatilities, mobilization/redemption churn, and RBI macroeconomic factors (repo rate changes, call money rates). All transforms are strictly isolated to prevent future data leakage.
3. **Forecasting Suite**: Four distinct model families evaluated for direct 3-step forecasting:
   - **Seasonal-Naive**: 12-month seasonal persistence baseline.
   - **ETS**: Exponential smoothing with additive error and trend.
   - **SARIMAX**: Seasonal autoregressive integrated moving average with calendar and macro exogenous regressors.
   - **Ridge Regression**: Regularized linear model with direct multi-horizon heads.
4. **Leak-Free Rolling-Origin Backtesting**: 24 expanding origins from July 2024 to June 2026 generating 576 evaluation records. Parameter fitting, feature generation, scaling, and error calibration strictly use information realized prior to each origin $T$.
5. **Prediction Interval Calibration**: Horizon-specific prediction intervals constructed from expanding archives of genuine out-of-sample forecast errors ($e = \text{Actual} - \text{Forecast}$), cutting off empirical percentiles ($q_{0.10}, q_{0.90}$ for 80% two-sided intervals; $q_{0.025}, q_{0.975}$ for 95% two-sided intervals).
6. **Cash Buffer Recommendation Engine**: Treasury sizing formula:
   $$\text{Recommended Buffer}_h = \max\left( \text{Base Operational Floor}, \; \text{Peak Cumulative Downside Deficit}_h \right)$$
   where Base Floor $= b_{\text{base}} \times \text{AUM}_T$, and Peak Deficit tracks $\max_{k=1..h} \left( \max(0, -\sum_{j=1}^k \hat{L}_{T+j}) \right)$, ensuring early liquidity shortfalls cannot be erased by subsequent inflows.

---

## Principal Findings & Forward Recommendations (Origin 2026-09)

### 1. Liquid Funds (Current AUM: ₹625,847.01 Cr)
- **Top Model**: SARIMAX outperforms Seasonal-Naive across all horizons (MAE: ₹27,618.17 Cr at 1M [+14.55% skill], ₹31,619.84 Cr at 2M [+1.26% skill], ₹33,086.53 Cr at 3M [+0.34% skill]; Pooled MAE: ₹30,774.85 Cr [+5.35% skill score]).
- **Tax Cycle Anticipation**: SARIMAX correctly anticipates the severe December advance tax drainage (-₹50,618.62 Cr point forecast, lower bound -₹91,294.66 Cr).
- **Forward Buffer Recommendations**:
  - **Horizon 1 (Oct 2026)**: Post-quarter rebound (+₹75,820.52 Cr). Deficit is ₹0. Buffer = **₹31,292.35 Cr (5.00% of AUM)** governed by base floor.
  - **Horizon 2 (Oct–Nov 2026)**: Buffer = **₹31,292.35 Cr (5.00% of AUM)** governed by base floor.
  - **Horizon 3 (Oct–Dec 2026)**: Peak downside deficit expands ahead of December corporate tax outflow:
    - *Moderate (80% 2-Sided / 90% Downside)*: **₹75,072.74 Cr (12.00% of AUM)**.
    - *Conservative (95% 2-Sided / 97.5% Downside)*: **₹106,161.75 Cr (16.96% of AUM)**.

### 2. Overnight Funds (Current AUM: ₹84,032.57 Cr)
- **High Turnover Reality**: Gross monthly turnover exceeds 500% of AUM (>₹400,000 Cr gross redemptions monthly).
- **Top Models**: SARIMAX is preferred at Horizon 1 (MAE ₹13,941 Cr); Seasonal-Naive is preferred at Horizons 2 & 3 (MAE ₹16,076 Cr and ₹15,804 Cr).
- **Forward Buffer Recommendations (Single-Model Trajectory Baseline)**:
  - **Horizon 1 (Oct 2026, `SARIMAX`)**: Point forecast +₹16,981.99 Cr, lower bound -₹10,366.04 Cr.
    - *Moderate*: **₹10,366.04 Cr (12.34% of AUM)**.
    - *Conservative*: **₹17,606.86 Cr (20.95% of AUM)**.
  - **Horizon 2 (Oct–Nov 2026, `Seasonal-Naive`)**:
    - *Moderate*: **₹53,023.40 Cr (63.10% of AUM)**.
    - *Conservative*: **₹80,982.57 Cr (96.37% of AUM)**.
  - **Horizon 3 (Oct–Dec 2026, `Seasonal-Naive`)**:
    - *Moderate*: **₹74,130.35 Cr (88.22% of AUM)**.
    - *Conservative*: **₹118,049.89 Cr (140.48% of AUM)**.
- **Alternative Step-Wise Stitched Trajectory (`step_wise_preferred=True`)**:
  - Stitches step-wise best models ($k=1$ SARIMAX, $k=2,3$ Seasonal-Naive) with strictly matched error quantiles per step:
    - *Moderate*: **₹90,640.30 Cr (107.86% of AUM)**.
    - *Conservative*: **₹129,620.28 Cr (154.25% of AUM)**.

### 3. Outlier Sensitivity Note: Overnight Fund Multi-Month Buffer
The 3-month Overnight Fund cash buffer recommendation (₹74,130.35 Cr moderate / ₹118,049.89 Cr conservative) is **heavily sensitive to the November 2025 historical outlier (-₹37,624.53 Cr)** recorded in AMFI data:
- Because Seasonal-Naive repeats the 12-month-old observation, its Month 2 point forecast is -₹37,624.53 Cr.
- Adding the empirical 10th percentile error (-₹21,542.78 Cr) yields a Month 2 downside projection of -₹59,167.31 Cr.
- Cumulative deficit aggregation assumes this adverse shock is compounded with Month 3 downside (-₹21,106.95 Cr), producing a cumulative downside shortfall of ₹74,130.35 Cr.
- **Analytical Integrity**: This outlier and its downstream effect are preserved without artificial smoothing to provide uncompromised visibility into how extreme historical tail events influence quantitative treasury models under comonotonic stress assumptions.

---

## Methodological Limitations & Governance Safeguards

1. **Marginal Intervals vs. Comonotonic Stress Scenarios**:
   - Monthly prediction bounds $\hat{L}_{T+j}^{(\alpha)}$ represent marginal 10th or 2.5th percentiles calibrated on historical out-of-sample errors.
   - Summing monthly lower bounds ($\sum \hat{L}$) assumes **comonotonicity** (perfect positive dependence across months), modeling an extreme scenario where adverse tail shocks strike every single month consecutively.
   - The multi-month buffer is formally classified as a **conservative comonotonic stress scenario**, not a calibrated joint multi-month prediction interval.
2. **Monthly Net Flows vs. Intraday Corporate Runs**:
   - AMFI datasets report monthly aggregate flows. Severe intraday cash runs (e.g. concentrated institutional withdrawals around the 15th–18th of tax months) are not captured in monthly aggregates and require complementary intraday liquidity monitoring.
3. **No Financial Guarantee**:
   - The cash buffer recommendation is an advisory treasury decision-support tool. Historical interval coverage reflects empirical backtest performance under normal and cyclical market conditions, but does not constitute an unconditional financial guarantee against systemic black-swan credit events, sovereign repo freezes, or institutional panic runs.

## Problem Statement Summary

Indian liquid and overnight mutual funds experience significant flow volatility driven by factors such as RBI policy rates, call-money rates, GST and advance-tax outflow cycles, corporate treasury behaviour, and broader equity-market sentiment. Accurate short-term (3-month) flow forecasting enables fund managers to pre-position liquidity and reduce transaction costs.

## Licence

MIT

