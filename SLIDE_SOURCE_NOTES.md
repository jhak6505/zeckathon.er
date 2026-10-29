# FINHYPE — Presentation Slide Source Notes & Data Provenance

**Document ID:** FINHYPE-SLIDE-SOURCE-NOTES-2026-10-29  
**Presentation:** `FINHYPE_Zeckathon_2026.pptx` (9 Slides, 16:9 Widescreen)  
**Hackathon:** Zeckathon 2026 · Problem Statement 3  
**Forecast Origin:** September 2026 (`2026-09`)  
**Forward Forecast Horizon:** October, November, December 2026 (`2026-10`, `2026-11`, `2026-12`)  
**Currency Units:** INR Crore (₹ Cr) unless stated as percentage  

---

## Slide 1: Title and One-Line Value Proposition

| Quantitative Claim / Metric | Exact Value | Units / Scope | Source File / Artifact | Line Reference / Function |
|:---|:---|:---|:---|:---|
| **Historical Data Coverage** | 90 consecutive months (April 2019 – September 2026) | Months | `data/processed/fund_flows_monthly.csv` | Lines 1–181 (90 rows per category) |
| **Category Record Count** | 180 total records (90 Liquid + 90 Overnight) | Database records | `data/finhype.db` | Table `fund_flows_monthly` (`app/data/db.py`, `tests/test_db.py`) |
| **Automated Test Count** | 154 passing unit & integration tests (100% pass rate in ~12.1s) | Tests | `tests/` | `pytest -v` across 12 test modules |
| **Combined Sector AUM** | ₹7,09,879.58 Cr (Liquid: ₹6,25,847.01 Cr + Overnight: ₹84,032.57 Cr) | ₹ Crore (Sep 2026) | `data/processed/fund_flows_monthly.csv` | Rows 90 & 180 (`aum_cr` column) |
| **Rolling Backtest Scope** | 24 origins (July 2024 – June 2026), 576 prediction records | Evaluation records | `data/processed/backtest_results.csv` | 24 origins × 2 categories × 4 models × 3 horizons |

---

## Slide 2: The Liquidity Sizing Problem

| Quantitative Claim / Metric | Exact Value | Units / Scope | Source File / Artifact | Line Reference / Function |
|:---|:---|:---|:---|:---|
| **Liquid Funds AUM** | ₹6,25,847.01 Cr | ₹ Crore (Sep 2026) | `data/processed/fund_flows_monthly.csv` | Liquid Fund row for `2026-09` |
| **Liquid Monthly Redemptions** | Mean: **₹4,63,686 Cr (104.1% of AUM; median 74.2%)**; Range: ₹2.11L Cr – ₹20.98L Cr | Monthly redemptions | `data/processed/fund_flows_monthly.csv` | `redemption_cr` column |
| **Liquid Gross Monthly Volume** | Mean: **₹9,27,836 Cr (207.3% of AUM; median 155.7%)** | Total turnover | `data/processed/fund_flows_monthly.csv` | `funds_mobilised_cr + redemption_cr` |
| **Liquid Projected Dec 2026 Net Drain** | -₹50,618.62 Cr (Point forecast); -₹89,235.07 Cr (Lower 80% bound) | ₹ Crore | `data/processed/forward_forecasts_3m.csv` | Row 10: `SARIMAX`, `horizon=3`, `target_month=2026-12` |
| **Overnight Funds AUM** | ₹84,032.57 Cr | ₹ Crore (Sep 2026) | `data/processed/fund_flows_monthly.csv` | Overnight Fund row for `2026-09` |
| **Overnight Monthly Redemptions** | Mean: **₹4,21,786 Cr (544.7% of AUM; median 504.2%)**, turning over **5.45x of AUM monthly** | Monthly redemptions | `data/processed/fund_flows_monthly.csv` | `redemption_cr` column |
| **Overnight Gross Monthly Volume** | Mean: **₹8,43,975 Cr (1,089.0% of AUM; median 1,017.4%)** | Total turnover | `data/processed/fund_flows_monthly.csv` | `funds_mobilised_cr + redemption_cr` |
| **Velocity Gap** | Overnight Funds turn over their asset base **>5x faster** than Liquid Funds | Portfolio velocity ratio | `data/processed/fund_flows_monthly.csv` | Contrast: 545% vs. 104% |
| **Overnight Historic Outflow Outlier** | -₹37,624.53 Cr (recorded in November 2025) | ₹ Crore | `data/processed/fund_flows_monthly.csv` | Overnight Fund row for `2025-11` |

---

## Slide 3: Data Sources and Validation

| Quantitative Claim / Metric | Exact Value | Units / Scope | Source File / Artifact | Line Reference / Function |
|:---|:---|:---|:---|:---|
| **AMFI Historical Span** | 90 continuous months (April 2019 – September 2026) | Time series | `app/data/amfi_scraper.py` | `fetch_report_links()`, `parse_month_label()` |
| **Accounting Invariance Tolerance** | $\le 0.01\text{ Cr}$ ($|\text{Net Flow} - (\text{Mobilised} - \text{Repurchase})| \le 0.01$) | ₹ Crore tolerance | `app/data/amfi_validator.py` | `validate_amfi_dataset()`, Line 55 |
| **Missing Values / Interpolation** | Exactly 0 nulls, 0 missing records across all 180 rows | Count | `tests/test_data_integrity_audit.py` | `test_production_csv_artifacts_continuity_and_completeness` |
| **Engineered Features Count** | 53 domain-engineered indicators | Features | `app/forecasting/feature_engineering.py` | `build_feature_pipeline()`, feature manifest |
| **RBI Repo Rate Corridor** | **4.00% to 6.50%** (pandemic low: 4.00% [May 2020 – Apr 2022], peak tightening: 6.50% [Feb 2023 – Jan 2025], easing cycle to 5.25% [Dec 2025 – Sep 2026]) | Percentage | `data/processed/external_factors_monthly.csv` | `repo_rate_pct` column |
| **Forward Macro Assumption** | $\Delta \text{Repo}_{T+h} = 0$, $\text{Nifty Return}_{T+h} = 0$ for $h \in \{1, 2, 3\}$ | Policy assumption | `app/services/forward_forecasting.py` | `generate_forward_calendar()` |

---

## Slide 4: System Architecture

| Quantitative Claim / Metric | Exact Value | Units / Scope | Source File / Artifact | Line Reference / Function |
|:---|:---|:---|:---|:---|
| **Pipeline Architecture Stages** | 6 distinct modular stages | Stages | `ARCHITECTURE.md` | Section 1, Mermaid Diagram (Stages 1–6) |
| **Temporal Lag Separation** | Lags (`_lag_1`, `_lag_12`) use strictly shifted vectors (`.shift(1)`) | Indicator logic | `app/forecasting/feature_engineering.py` | `add_autoregressive_lags()` |
| **StandardScaler Fitting Window** | $t \le T$ (strictly historical training slice) | Data window | `app/forecasting/models.py` | `RidgeDirectForecaster.fit(train_df)` |
| **Future Mutation Invariance Tolerance** | $\pm 10^{-5}\text{ Cr}$ (asserted via `np.testing.assert_allclose`) | Solver tolerance | `tests/test_audit_phase2.py` | `test_full_pipeline_end_to_end_leakage_invariance` |
| **One-Command Pipeline Execution** | 7 automated pipeline steps | Pipeline runner | `run_pipeline.py` | `main()`, steps 1 to 7 |

---

## Slide 5: Forecasting Models and Evaluation

| Quantitative Claim / Metric | Exact Value | Units / Scope | Source File / Artifact | Line Reference / Function |
|:---|:---|:---|:---|:---|
| **Model Families Evaluated** | 4 families: Seasonal-Naive, ETS, SARIMAX, Ridge Direct | Models | `app/forecasting/models.py` | `SeasonalNaiveForecaster`, `ETSForecaster`, etc. |
| **Backtest Origins Window** | 24 monthly origins: July 2024 (`2024-07`) to June 2026 (`2026-06`) | Months | `app/forecasting/backtest.py` | `run_rolling_origin_backtest()` |
| **Backtest Prediction Records** | 576 rows ($24 \times 2 \times 4 \times 3$) | Records | `data/processed/backtest_results.csv` | Verified by `test_backtest_origins_count_and_span` |
| **Prediction Interval Levels** | 80% ($q_{0.10}$ to $q_{0.90}$) and 95% ($q_{0.025}$ to $q_{0.975}$) | Quantiles | `app/forecasting/intervals.py` | `PredictionIntervalCalibrator.compute_intervals()` |
| **Temporal Admissibility Condition** | $\tau + h \le T$ (only realized target months admitted) | Invariant rule | `app/forecasting/intervals.py` | `compute_intervals()`, Lines 80–110 |
| **Interval Monotonicity Check** | $\text{lower}_{95} \le \text{lower}_{80} \le \hat{Y} \le \text{upper}_{80} \le \text{upper}_{95}$ | Assertions | `app/services/forward_forecasting.py` | `validate_point_forecast_and_interval_compatibility()` |

---

## Slide 6: Backtest Results

| Quantitative Claim / Metric | Exact Value | Units / Scope | Source File / Artifact | Line Reference / Function |
|:---|:---|:---|:---|:---|
| **Liquid Fund SARIMAX 1M MAE** | ₹27,618.17 Cr (RMSE: ₹35,765.32 Cr, WAPE: 44.12%, MASE: 0.7144) | ₹ Crore | `data/processed/backtest_metrics_summary.csv` | Row 10: `Liquid Fund`, `sarimax`, `horizon=1` |
| **Liquid Fund Seasonal-Naive 1M MAE** | ₹32,321.53 Cr (Baseline, Skill Score: 0.00%) | ₹ Crore | `data/processed/backtest_metrics_summary.csv` | Row 2: `Liquid Fund`, `seasonal_naive`, `horizon=1` |
| **Liquid Fund SARIMAX 1M Skill Score** | **+14.55%** error reduction over Seasonal-Naive | Percentage | `data/processed/backtest_metrics_summary.csv` | Row 10: `skill_score = (MAE_base - MAE_model)/MAE_base` |
| **Liquid Fund ETS 1M MAE / Skill** | ₹41,157.21 Cr / -27.34% Skill Score | ₹ Crore / % | `data/processed/backtest_metrics_summary.csv` | Row 6: `Liquid Fund`, `ets`, `horizon=1` |
| **Liquid Fund Ridge 1M MAE / Skill** | ₹60,698.15 Cr / -87.79% Skill Score | ₹ Crore / % | `data/processed/backtest_metrics_summary.csv` | Row 14: `Liquid Fund`, `ridge`, `horizon=1` |
| **Overnight Fund SARIMAX 1M MAE** | **₹13,940.84 Cr** vs. ₹15,090.39 Cr for Seasonal-Naive (**+7.62% Skill**) | ₹ Crore | `data/processed/backtest_metrics_summary.csv` | Row 26: `Overnight Fund`, `sarimax`, `horizon=1` |
| **Overnight Seasonal-Naive 2M MAE** | **₹16,076.12 Cr** vs. ₹16,743.27 Cr for SARIMAX (Top model at 2M) | ₹ Crore | `data/processed/backtest_metrics_summary.csv` | Row 19: `Overnight Fund`, `seasonal_naive`, `horizon=2` |
| **Overnight Seasonal-Naive 3M MAE** | **₹15,804.12 Cr** vs. ₹16,011.27 Cr for SARIMAX (Top model at 3M) | ₹ Crore | `data/processed/backtest_metrics_summary.csv` | Row 20: `Overnight Fund`, `seasonal_naive`, `horizon=3` |
| **Liquid Forward Forecasts (SARIMAX for h=1..3)** | Oct: **+₹75,820.52 Cr** (rebound); Nov: **-₹8,979.98 Cr**; Dec: **-₹50,618.62 Cr** (tax drain, lower 80% bound: -₹89,235.07 Cr) | ₹ Crore | `data/processed/forward_forecasts_3m.csv` | Rows 8–10 (`sarimax`) |
| **Overnight Forward Forecasts (Horizon Split)** | Horizon 1: **+₹16,981.99 Cr** (SARIMAX preferred; lower 80%: -₹10,366.04 Cr); Horizons 2 & 3: **-₹37,624.53 Cr** & **+₹254.25 Cr** (Seasonal-Naive preferred) | ₹ Crore | `data/processed/forward_forecasts_3m.csv` | Row 20 (`sarimax` h=1) and Rows 15–16 (`seasonal_naive` h=2,3) |
| **Table Scope Disclosure** | Slide 6 table is a **Selected Benchmark Summary (10 rows)** highlighting 1M cross-model comparisons and winning multi-step trajectories; complete 32-row evaluation is archived in `backtest_metrics_summary.csv`. | Scope definition | `data/processed/backtest_metrics_summary.csv` | 32 total evaluation rows across all models/horizons |
| **Marginal vs. Joint Multi-Month Coverage** | Marginal 80% coverage: **76.04%** (Liquid) / **72.22%** (Overnight); Marginal 95% coverage: **87.50%** (Liquid) / **83.33%** (Overnight). Joint 3-month simultaneous coverage: **45.83%–50.00%** (80%) and **58.33%–79.17%** (95%), mathematically supporting comonotonic stress aggregation over joint independence. | Statistical metric | `data/processed/backtest_results.csv` | Empirical evaluation across 24 rolling origins |

---

## Slide 7: Dynamic Cash-Buffer Engine

| Quantitative Claim / Metric | Exact Value | Units / Scope | Source File / Artifact | Line Reference / Function |
|:---|:---|:---|:---|:---|
| **Liquid Base Operational Floor (5.0%)** | ₹31,292.35 Cr ($5.0\% \times ₹6,25,847.01\text{ Cr}$) | ₹ Crore | `app/services/cash_buffer.py` | `get_default_base_buffer_pct()`, Line 35 |
| **Liquid 1M Buffer (Oct 2026)** | **₹31,292.35 Cr (5.00% AUM)** [Downside deficit is ₹0; floor-driven] | ₹ Crore (% AUM) | `app/services/forward_forecasting.py` | `get_forward_recommendation("Liquid Fund", 1)` |
| **Liquid 2M Buffer (Oct–Nov 2026)** | **₹31,292.35 Cr (5.00% AUM)** [Cum downside is +₹14,162 Cr; floor-driven] | ₹ Crore (% AUM) | `app/services/forward_forecasting.py` | `get_forward_recommendation("Liquid Fund", 2)` |
| **Liquid 3M Moderate Buffer (80%)** | **₹75,072.74 Cr (12.00% AUM)** [Cumulative deficit reaches ₹75,073 Cr] | ₹ Crore (% AUM) | `app/services/forward_forecasting.py` | `get_forward_recommendation("Liquid Fund", 3, "moderate")` |
| **Liquid 3M Conservative Buffer (95%)** | **₹106,161.75 Cr (16.96% AUM)** [Cumulative deficit reaches ₹106,162 Cr] | ₹ Crore (% AUM) | `app/services/forward_forecasting.py` | `get_forward_recommendation("Liquid Fund", 3, "conservative")` |
| **Overnight Base Floor (2.5%)** | ₹2,100.81 Cr ($2.5\% \times ₹84,032.57\text{ Cr}$) | ₹ Crore | `app/services/cash_buffer.py` | `get_default_base_buffer_pct()`, Line 37 |
| **Overnight 1M Buffer (Oct 2026, SARIMAX)** | Moderate: **₹10,366.04 Cr (12.34% AUM)**; Conservative: **₹17,606.86 Cr (20.95%)** | ₹ Crore (% AUM) | `app/services/forward_forecasting.py` | `get_forward_recommendation("Overnight Fund", 1)` |
| **Overnight 3M Single Baseline (S-Naive)** | Moderate: **₹74,130.35 Cr (88.22% AUM)**; Conservative: **₹118,049.89 Cr (140.48%)** | ₹ Crore (% AUM) | `app/services/forward_forecasting.py` | `get_forward_recommendation(..., step_wise_preferred=False)` |
| **Overnight 3M Stitched Alternative** | Moderate: **₹90,640.30 Cr (107.86% AUM)**; Conservative: **₹129,620.28 Cr (154.25%)** | ₹ Crore (% AUM) | `app/services/forward_forecasting.py` | `get_forward_recommendation(..., step_wise_preferred=True)` |

---

## Slide 8: Live Dashboard Demonstration

| Feature / Artifact | Description & Parameter Values | Source File / Implementation | Line Reference / Function |
|:---|:---|:---|:---|
| **Tab 3 Default Model Dropdown** | `🛡️ Active Cash-Buffer Policy Trajectory` (dynamically feeds Tab 4) | `app/dashboard.py` | Lines 353–395 (`fwd_model == "policy_trajectory"`) |
| **Tab 3 Responsive Sub-Tabs** | 3 dedicated views: `Complete Summary`, `Moderate Risk (80%)`, `Conservative Stress (95%)` | `app/dashboard.py` | Lines 455–510 (`st.tabs()`, `hide_index=True`) |
| **Tab 4 Monthly Progression Table** | Explicit columns: `Step`, `Month`, `Model`, `Forecast`, `Downside`, `Cumulative Deficit` | `app/dashboard.py` | Lines 710–740 (`df_rec_breakdown`) |
| **Overnight Policy Expander** | Live comparison of Single-Model Baseline vs. Step-Wise Stitched Alternative | `app/dashboard.py` | Lines 525–545 (`st.expander()`) |
| **Dashboard Startup Time** | Loads precomputed processed artifacts in `< 1.0s` via `@st.cache_data` | `app/dashboard.py` | Lines 50–110 (`load_data()`) |
| **Launch Command Scripts** | `.\run.ps1 -OnlyDashboard` (PowerShell) / `.\run.bat --only-dashboard` (CMD) | `run.ps1`, `run.bat` | Production wrapper scripts forwarding CLI arguments |

---

## Slide 9: Limitations, Governance, and Conclusion

| Governance Boundary / Disclosure | Underlying Mathematical Condition | Reference Document | Detailed Section |
|:---|:---|:---|:---|
| **Comonotonic Stress Assumption** | Summing monthly downside bounds ($\sum_{j=1}^k \hat{L}_{T+j}$) assumes perfect positive tail dependence across consecutive months, modeling an extreme adverse shock sequence rather than a joint multi-month probability distribution. | `LIMITATIONS.md` | Section 2.1 ("Comonotonic Deficit Aggregation vs. Joint Probability Intervals") |
| **Sample Size Granularity ($N=24$)** | 24 rolling origins means each error is $1/24 \approx 4.17\%$ of the empirical distribution. Nominal 80% and 95% levels are empirical calibration heuristics, not asymptotic mathematical proofs against unobserved market regimes. | `LIMITATIONS.md` | Section 2.2 ("Sample Size Granularity in Out-of-Sample Calibration") |
| **Monthly vs. Intraday Runs** | Monthly AMFI data cannot resolve intraday liquidity runs around the 15th of tax months; intraday solvency relies on the Base Operational Floor and repo credit lines. | `LIMITATIONS.md` | Section 2.3 ("Monthly Aggregation vs. Intraday Corporate Runs") |
| **November 2025 Historical Outlier** | Severe historical outflow of -₹37,624.53 Cr in Overnight Funds is carried forward by Seasonal-Naive, producing a Conservative buffer >100% of AUM under comonotonic stress. Preserved without artificial smoothing for analytical transparency. | `LIMITATIONS.md` | Section 2.4 ("Sensitivity to Extreme Historical Regime Shifts") |
| **Constant Forward Macro Assumption** | Forward multi-step projections assume $\Delta \text{Repo} = 0$, preventing speculative bets on unannounced RBI decisions. | `LIMITATIONS.md` | Section 2.5 ("Exogenous Macroeconomic Projections") |
| **System Certified Acceptance** | 154 unit and integration tests passing; zero data leakage; bit-for-bit dashboard/service parity; zero implementation blockers. | `RELEASE_CHECKLIST.md` | Section 1 ("Automated Quality & Integrity Gates") |

