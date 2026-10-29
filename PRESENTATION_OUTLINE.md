# FINHYPE — Final Technical Presentation Outline

**Project:** FINHYPE (Zeckathon 2026 · Problem Statement 3)  
**Title:** Quantitative Treasury Liquidity Forecasting & Risk-Calibrated Buffer Sizing  
**Target Audience:** Technical Judging Panel, Quantitative Evaluators, and Treasury Risk Managers  
**Format:** 9-Slide Structured Technical Presentation (Accompanies 5-Minute Pitch)  
**Forecast Origin:** September 2026 | **Forecast Horizon:** October, November, December 2026  

---

## Slide 1: Problem — The Mutual-Fund Liquidity-Planning Dilemma

### Title
**The Liquidity Sizing Dilemma in Indian Debt & Money Market Funds**

### Key Points
* **Structural Flow Volatility:** Indian mutual funds face predictable, severe cyclical drains driven by quarterly corporate advance-tax installments (March, June, September, December) followed by immediate post-quarter corporate reinvestment surges (April, July, October, January).
* **Extreme Velocity in Money Markets:** Liquid Funds (~₹6.26 lakh Cr AUM) and Overnight Funds (~₹84,000 Cr AUM) exhibit high liquidity velocity. In Overnight Funds, monthly gross turnover exceeds **540% of fund AUM** (>₹4.2 lakh Cr in monthly redemptions).
* **The Cost of Liquidity Miscalculation:** 
  * *Under-buffering* forces distressed fire-sales of short-term commercial papers or costly emergency borrowing in overnight repo markets.
  * *Over-buffering* creates severe cash drag, depressing annualized fund yields in ultra-competitive basis-point markets.
* **The Core Gap:** Point forecasting alone tells treasurers *expected* flow, but cannot answer: *"How much liquid cash must be held today to survive worst-case cumulative outflows over the next 1 to 3 months?"*

### Recommended Visual
* **Split Graphic:**
  * Left: Historical Net Flow Seasonality Profile (bar chart highlighting recurring negative tax months vs. positive post-quarter inflows).
  * Right: AUM vs. Monthly Gross Turnover bar chart illustrating the 5.44x portfolio velocity in Overnight Funds.

### Speaker Notes
> "Good morning, judges. In the Indian mutual fund industry, liquidity management is not a passive exercise—it is a high-stakes balance between yield and solvency. In Liquid and Overnight funds, corporate treasuries treat fund units as operational current accounts, moving tens of thousands of crores in response to quarterly advance tax cycles. A point forecast tells you that December will see net redemptions, but point forecasts do not tell a treasury officer how much cash to hold today. FINHYPE solves this: an end-to-end quantitative system that forecasts 3-month net flows, estimates horizon-specific empirical uncertainty, and translates downside risk into an actionable, audit-defensible cash buffer."

### Source File & Evidence
* Flow seasonality & turnover: `data/processed/fund_flows_monthly.csv`
* Exploratory data analysis: [reports/figures/seasonality_monthly.html](file:///C:/Users/Alok/Desktop/FINHYPE/reports/figures/seasonality_monthly.html)
* Architecture context: [ARCHITECTURE.md](file:///C:/Users/Alok/Desktop/FINHYPE/ARCHITECTURE.md#L53-L69)

---

## Slide 2: Solution — What FINHYPE Predicts & How It Decides

### Title
**FINHYPE: From Machine Learning Forecasts to Treasury Action**

### Key Points
* **Dual Deliverable System:**
  1. *Quantitative Flow Forecasting*: 3-month multi-step forward net flow projections ($h=1, 2, 3$) for Liquid and Overnight funds.
  2. *Treasury Cash Buffer Engine*: Dynamic liquidity sizing parameterized by fund AUM, planning horizon, and institutional risk tolerance (Moderate 80% vs. Conservative 95%).
* **Non-Monotonic Cumulative Sizing:**
  $$\text{Recommended Buffer}_h = \max\left( \text{Base Operational Floor}, \; \text{Peak Cumulative Downside Deficit}_h \right)$$
* **Early Deficit Preservation:** Unlike naïve netting, early-horizon liquidity shortfalls cannot be masked or cancelled out by later-horizon projected inflows.
* **Empirical Integrity:** Zero reliance on Gaussian assumptions; uncertainty bounds are calibrated directly from genuine out-of-sample historical forecast errors.

### Recommended Visual
* **Concept Schematic:** Flow diagram showing Ingestion $\to$ Feature Engineering $\to$ Models $\to$ Rolling Backtest Error Calibration $\to$ Max(Operational Floor, Peak Deficit) $\to$ Final Buffer Recommendation Card.

### Speaker Notes
> "FINHYPE does not stop at generating machine learning forecasts. Our core innovation is translating multi-step probabilistic forecasts into a concrete treasury decision: exactly how many crores of liquid assets to hold. We combine a baseline operational cushion with a peak cumulative deficit rule. If a fund experiences a massive deficit in Month 1, subsequent projected inflows in Month 2 cannot erase the liquidity risk you faced on Day 30. Our engine preserves that maximum exposure across time."

### Source File & Evidence
* Recommendation engine: [app/services/cash_buffer.py](file:///C:/Users/Alok/Desktop/FINHYPE/app/services/cash_buffer.py#L90-L185)
* Forward forecasting integration: [app/services/forward_forecasting.py](file:///C:/Users/Alok/Desktop/FINHYPE/app/services/forward_forecasting.py#L204-L305)

---

## Slide 3: Data — AMFI Coverage, Accounting Validation & Macro Inputs

### Title
**Data Foundation: 90 Continuous Months & Multi-Stage Validation**

### Key Points
* **Primary Time Series:** 90 continuous monthly AMFI statements (April 2019 – September 2026; 180 fund-category records).
* **Automated Data Quality & Accounting Invariance:**
  * Excel/HTML scraper with regex header normalization across 7+ years of reporting changes.
  * Invariant accounting check: $|\text{Net Flow} - (\text{Funds Mobilised} - \text{Repurchases})| \le 0.01\text{ Cr}$.
  * SQLite transactional ingestion (`data/finhype.db`) with composite unique constraints on `(month, category)` preventing duplicate records.
* **Exogenous Macroeconomic Drivers:**
  * RBI Monetary Policy Committee Repo Rate decisions (4.00% pandemic low to 6.50% peak corridor [Feb 2023 – Jan 2025]; eased to 5.25% at Sep 2026 origin).
  * NSE Nifty 50 equity benchmark monthly returns and market volatility.
* **Temporal Protection:** Future macro changes are held neutral ($\Delta \text{Repo}_{T+h} = 0$), strictly barring future policy speculation from contaminating forecasts.

### Recommended Visual
* **Dual Time Series Chart:** 90-month historical net flow trajectories for Liquid Funds vs. Overnight Funds, annotated with RBI rate hiking cycles (2022–2023) and quarterly advance-tax outflow troughs.

### Speaker Notes
> "A quantitative model is only as credible as its data engineering. We ingested 90 consecutive months of official AMFI statements spanning April 2019 to September 2026. Because AMFI formats shifted multiple times over 7 years, we built a resilient parser paired with a zero-tolerance accounting validator: gross mobilization minus gross redemptions must equal net flow within 1 lakh rupees, or the batch transaction rolls back. We augment this with RBI policy rates and Nifty 50 equity returns, while strictly assuming flat future policy rates so no macro speculation leaks into forward models."

### Source File & Evidence
* Database & schema: [app/data/db.py](file:///C:/Users/Alok/Desktop/FINHYPE/app/data/db.py#L1-L120)
* Scraper & validator: [app/data/amfi_validator.py](file:///C:/Users/Alok/Desktop/FINHYPE/app/data/amfi_validator.py#L1-L115)
* External macro factors: [app/data/external_factors.py](file:///C:/Users/Alok/Desktop/FINHYPE/app/data/external_factors.py#L1-L150)

---

## Slide 4: System Architecture — 6-Stage Temporal Leakage-Free Design

### Title
**End-to-End System Architecture with Strict Temporal Isolation**

### Key Points
* **Modular 6-Stage Pipeline:**
  1. *AMFI Ingestion & Validation* $\to$ 2. *Feature Engineering (53 indicators)* $\to$ 3. *Forecasting & 24-Origin Backtest* $\to$ 4. *Empirical Prediction Intervals* $\to$ 5. *Cash Buffer Engine* $\to$ 6. *Streamlit Presentation*.
* **Leakage-Free Feature Transformation:**
  * All autoregressive lags and rolling statistics use strictly shifted series (`.shift(1)`), preventing observation at $t$ from appearing in features at $t$.
  * Standardization scalers (`StandardScaler`) in direct regression are fitted exclusively on training slices ($t \le T$).
* **Future Data Mutation Invariance Test:**
  * Production leakage test (`test_audit_phase2.py`) mutates historical data occurring *after* origin $T$ and asserts that past forecasts and interval bounds remain invariant within numerical solver tolerance ($\pm 10^{-5}\text{ Cr}$).
* **Execution Automation:** Unified one-command execution via `run_pipeline.py`, PowerShell (`run.ps1`), and CMD (`run.bat`).

### Recommended Visual
* **Mermaid Architecture Diagram:** High-level 6-stage architecture diagram matching [ARCHITECTURE.md](file:///C:/Users/Alok/Desktop/FINHYPE/ARCHITECTURE.md#L14-L47).

### Speaker Notes
> "Temporal data leakage is the silent killer of financial time-series models. We engineered FINHYPE with strict mathematical boundaries. Every feature—from rolling 6-month volatility to advance tax flags—is computed exclusively on shifted historical vectors. When scaling features, scikit-learn transformers are fit strictly on data up to origin T. We validated this with an automated future-data mutation test: modifying future records produces invariant historical forecasts, confirmed across 154 passing automated tests."

### Source File & Evidence
* Architecture specification: [ARCHITECTURE.md](file:///C:/Users/Alok/Desktop/FINHYPE/ARCHITECTURE.md#L10-L48)
* Leakage test verification: `tests/test_audit_phase2.py::test_full_pipeline_end_to_end_leakage_invariance`
* Automated test suite: 154 passed in 22.22s (`tests/`)

---

## Slide 5: Methodology — Forecasting Suite & Out-of-Sample Calibration

### Title
**Diverse Model Architectures & Genuine Out-of-Sample Error Calibration**

### Key Points
* **Four Diverse Model Families:**
  1. *Seasonal-Naive*: Annual 12-month cyclical persistence baseline ($\hat{Y}_{T+h} = Y_{T+h-12}$).
  2. *ETS*: Exponential Smoothing state-space model with additive trend and damped errors.
  3. *SARIMAX*: $(p,d,q) \times (P,D,Q)_{12}$ ARIMA incorporating forward deterministic calendar regressors.
  4. *Ridge Regression*: L2-regularized linear heads with direct multi-horizon forecasting ($h=1, 2, 3$).
* **24-Origin Expanding Rolling Backtest:**
  * Evaluated across 24 historical forecast origins (July 2024 through June 2026), generating 576 out-of-sample predictions.
* **Empirical Prediction Interval Calibration:**
  * Residual error defined as genuine out-of-sample forecast error: $e_{\tau, h} = Y_{\tau+h} - \hat{Y}_{\tau+h|\tau}$.
  * Temporal filtering: error $e_{\tau, h}$ enters calibration pool at origin $T$ if and only if $\tau + h \le T$.
  * Two-sided intervals: 80% ($q_{0.10}$ to $q_{0.90}$) and 95% ($q_{0.025}$ to $q_{0.975}$). In-sample residuals are strictly prohibited.

### Recommended Visual
* **Visual Diagram:** Expanding rolling-origin timeline showing the training window expanding from July 2024 to June 2026, with the 3-step forecast horizon advancing forward and out-of-sample errors accumulating without future lookahead.

### Speaker Notes
> "We chose four distinct model families representing distinct statistical inductive biases: simple seasonal persistence, state-space exponential smoothing, dynamic autoregression with exogenous calendar drivers, and regularized direct regression. Rather than relying on theoretical normal distributions, we calibrate prediction intervals using genuine out-of-sample forecast errors from our 24 rolling backtest origins. An error is only admitted into the calibration archive once its target month has been fully realized in historical time."

### Source File & Evidence
* Model definitions: `app/forecasting/models.py`
* Rolling backtest protocol: [app/forecasting/backtest.py](file:///C:/Users/Alok/Desktop/FINHYPE/app/forecasting/backtest.py#L1-L150)
* Interval calibrator: [app/forecasting/intervals.py](file:///C:/Users/Alok/Desktop/FINHYPE/app/forecasting/intervals.py#L1-L120)

---

## Slide 6: Results — Audited Backtest Benchmarks & Forward Projections

### Title
**Empirical Model Hierarchy & Forward Net Flow Projections (Origin: Sep 2026)**

### Key Points
* **Liquid Funds — SARIMAX Dominance:**
  * **Horizon 1 ($h=1$)**: MAE ₹27,618 Cr (**+14.55% Skill Score** over Seasonal-Naive; MASE = 0.7144).
  * **Horizon 2 ($h=2$)**: MAE ₹31,620 Cr (+1.26% Skill Score).
  * **Horizon 3 ($h=3$)**: MAE ₹33,087 Cr (+0.34% Skill Score).
  * Correctly models the severe **December advance-tax drainage** ($-₹50,619\text{ Cr}$ point forecast, lower bound $-₹89,235\text{ Cr}$).
* **Overnight Funds — Horizon-Dependent Champion:**
  * **Horizon 1 ($h=1$)**: SARIMAX preferred (MAE ₹13,941 Cr vs. ₹15,090 Cr for Seasonal-Naive, **+7.62% Skill Score**).
  * **Horizons 2 & 3 ($h=2, 3$)**: Seasonal-Naive preferred (MAE ₹16,076 Cr and ₹15,804 Cr), capturing year-over-year persistence better than parameterized models.
* **3-Month Forward Forecast Summary (Origin: 2026-09):**
  * *Liquid Fund (SARIMAX)*: Oct $+₹75,821\text{ Cr}$ (rebound), Nov $-₹8,980\text{ Cr}$, Dec $-₹50,619\text{ Cr}$ (tax drain).
  * *Overnight Fund (SARIMAX / Seasonal-Naive)*: Oct $+₹16,982\text{ Cr}$ / $+₹24,051\text{ Cr}$, Nov $-₹37,625\text{ Cr}$ (outlier persistence), Dec $+₹254\text{ Cr}$.

### Recommended Visual
* **Two-Panel Graphic:**
  * Top: Grouped bar chart comparing MAE across all 4 models and 3 horizons for Liquid and Overnight funds.
  * Bottom: 3-Month Forward Projections Trajectory Chart for Liquid Funds with 80% (Moderate) and 95% (Conservative) prediction fan bands.

### Speaker Notes
> "The empirical backtest results reveal striking domain insights. In Liquid Funds, SARIMAX beats all models across every horizon, delivering a 14.55% error reduction at Horizon 1. Its exogenous tax regressors allow it to anticipate the massive corporate liquidity drain in December. In Overnight Funds, the model hierarchy is horizon-dependent: SARIMAX wins at 1 month, but simple Seasonal-Naive persistence outperforms all complex models at months 2 and 3. We let the empirical backtest evidence govern model selection rather than forcing a single model everywhere."

### Source File & Evidence
* Audited backtest summary: [data/processed/backtest_metrics_summary.csv](file:///C:/Users/Alok/Desktop/FINHYPE/data/processed/backtest_metrics_summary.csv#L1-L33)
* Forward forecasts: [data/processed/forward_forecasts_3m.csv](file:///C:/Users/Alok/Desktop/FINHYPE/data/processed/forward_forecasts_3m.csv#L1-L25)

---

## Slide 7: Cash Buffer Engine — Sizing Under Comonotonic Stress

### Title
**Risk-Calibrated Buffer Sizing & Dual Overnight Policy Trajectories**

### Key Points
* **Two-Tier Sizing Formulation:**
  $$\text{Buffer} = \max(\text{Base Operational Floor}, \; \text{Peak Cumulative Downside Deficit})$$
* **Liquid Funds (AUM: ₹625,847 Cr, Base Floor: 5.0% = ₹31,292 Cr):**
  * **1-Month (Oct 2026)**: Point $+₹75,821\text{ Cr}$, Deficit $₹0\text{ Cr} \implies$ **₹31,292 Cr (5.00% AUM)** [Floor-driven].
  * **3-Month (Oct–Dec 2026, Moderate 80%)**: Cumulative downside reaches $-₹75,073\text{ Cr} \implies$ **₹75,073 Cr (12.00% AUM)** [Tax-drain driven].
  * **3-Month (Oct–Dec 2026, Conservative 95%)**: Downside deficit reaches $-₹106,162\text{ Cr} \implies$ **₹106,162 Cr (16.96% AUM)**.
* **Overnight Funds (AUM: ₹84,033 Cr, Base Floor: 2.5% = ₹2,101 Cr):**
  * **1-Month Standalone (Oct 2026, SARIMAX)**: Moderate: **₹10,366 Cr (12.34% AUM)** | Conservative: **₹17,607 Cr (20.95% AUM)**.
  * **3-Month Single-Model Baseline (`Seasonal-Naive`)**: Moderate: **₹74,130 Cr (88.22% AUM)** | Conservative: **₹118,050 Cr (140.48% AUM)**.
  * **3-Month Step-Wise Stitched Alternative (`SARIMAX` + `Seasonal-Naive` + `Seasonal-Naive`)**: Moderate: **₹90,640 Cr (107.86% AUM)** | Conservative: **₹129,620 Cr (154.25% AUM)**.
* **Why Buffer Can Exceed 100% of AUM:** Overnight gross monthly turnover exceeds $540\%$ of AUM. Comonotonic aggregation compounding the severe November 2025 outlier ($-₹37,625\text{ Cr}$) with downside error quantiles models extreme gross redemption stress. We preserve this transparently without artificial caps.

### Recommended Visual
* **Waterfall / Progression Bar Chart:** Step-by-Step Cumulative Liquidity Trajectory showing monthly expected flow vs. downside bounds vs. cumulative deficit line with the red recommended buffer threshold.

### Speaker Notes
> "Here is the ultimate treasury deliverable. For Liquid Funds, Month 1 requires only our 5% operational floor (₹31,292 Cr) because October is a post-quarter cash surge. But looking forward 3 months into December's corporate tax drain, the engine expands the Moderate buffer to ₹75,073 Cr (12% of AUM) to absorb the projected liquidity contraction. For Overnight Funds, we provide both a Single-Model Baseline and a Step-Wise Stitched Alternative. Notice that under conservative comonotonic stress, the 3-month Overnight buffer exceeds 100% of fund AUM. That is not a bug—in an overnight fund where gross monthly turnover turns over the entire AUM 5 times every month, compounding an extreme historical shock models severe liquidity distress. We present this transparently rather than artificially capping it."

### Source File & Evidence
* Cash buffer engine: [app/services/cash_buffer.py](file:///C:/Users/Alok/Desktop/FINHYPE/app/services/cash_buffer.py#L90-L235)
* Financial calculations audit: [work.md](file:///C:/Users/Alok/Desktop/FINHYPE/work.md#L45-L120)
* Unit regression tests: `tests/test_financial_calculation_audit.py`

---

## Slide 8: Live Demonstration — Navigating the FINHYPE Platform

### Title
**Interactive Treasury Decision Support: Live Dashboard Walkthrough**

### Key Points
* **Designed for Real-World Treasury Review:**
  * **Tab 1: Executive Summary**: Headline AUM, current net flow, fund velocity, and immediate action buffer card.
  * **Tab 2: Historical Dynamics & AUM**: 90-month interactive time series and calendar seasonality profiles.
  * **Tab 3: 3-Month Forward Forecasts**: Fan bands and responsive 3-view breakdown table (*All Bands*, *Moderate 80%*, *Conservative 95%*) with `Active Cash-Buffer Policy Trajectory` toggle.
  * **Tab 4: Cash Buffer Recommendation Engine**: Real-time parameter sliders (Base Floor, Horizon, Risk Profile), cumulative deficit progression, and Single-Model vs. Stitched policy comparison expander.
  * **Tab 5: Model Benchmark & Backtest**: Audited 24-origin metrics, Skill Scores, and MASE comparisons.
  * **Tab 6: Data Freshness & Governance**: Data lineage, macro assumptions, and limitation disclosures.
* **Instant Startup & Fault Tolerance:** Precomputed artifacts load in `< 1.0s`; graceful error banners guide users if raw data requires regeneration.

### Recommended Visual
* **Dashboard Screenshots Collage:** Highlighting the new responsive sub-tabs in Tab 3, the metric cards and waterfall deficit chart in Tab 4, and the policy comparison expander.

### Speaker Notes
> "Our Streamlit dashboard is designed for treasury officers and risk committees. In Tab 1, executives immediately see current liquidity velocity and headline recommendations. In Tab 3, users can examine standalone model forecasts or toggle the Active Policy Trajectory that directly feeds into the buffer engine. In Tab 4, risk managers can adjust operational floors and risk profiles live, viewing the exact monthly deficit progression. And Tab 5 provides full auditability, showing backtest error distributions across all 24 historical origins."

### Source File & Evidence
* Dashboard source: [app/dashboard.py](file:///C:/Users/Alok/Desktop/FINHYPE/app/dashboard.py#L1-L834)
* Demonstration script: [DEMO_GUIDE.md](file:///C:/Users/Alok/Desktop/FINHYPE/DEMO_GUIDE.md#L63-L73)

---

## Slide 9: Limitations, Governance & Production Roadmap

### Title
**Analytical Integrity: Explicit Limitations & Production Enhancements**

### Key Points
* **What FINHYPE Does NOT Claim:**
  * *No Guaranteed Coverage*: Nominal 80%/95% confidence reflects historical frequency across $N=24$ origins; it is an empirical heuristic, not a mathematical guarantee against black-swan shocks.
  * *Comonotonic Assumption*: Summing monthly lower bounds assumes consecutive worst-case shocks; it represents an advisory stress scenario, not a calibrated joint probability distribution.
  * *Intraday Blind Spot*: Monthly AMFI data cannot capture intraday redemption spikes (e.g. corporate tax payments concentrated on the 15th of the month). Intraday buffers rely on the Base Operational Floor.
* **Analytical Transparency:** Historical outliers (such as November 2025's $-₹37,625\text{ Cr}$) are preserved without artificial smoothing to provide uncompromised visibility into tail risk.
* **Production Deployment Roadmap:**
  1. *Intraday Data Integration*: Ingesting daily AMFI NAVs and transaction-level RTGS redemption data.
  2. *Joint Multi-Horizon Copula Calibration*: Replacing comonotonic summation with vine copulas for non-linear multi-month joint dependence.
  3. *Dynamic Macro Scenario Engine*: Integrating live RBI MPC probability distributions and liquidity adjustment facility (LAF) balances.

### Recommended Visual
* **Summary Table:** Comparison table contrasting current implementation strengths vs. stated limitations vs. future production enhancements.

### Speaker Notes
> "We believe analytical integrity is the hallmark of serious quantitative engineering. We do not claim guaranteed coverage or immunity to tail shocks. With 24 backtest origins, each observation represents 4.2% of the empirical distribution, so nominal intervals are empirical calibration guides. Furthermore, summing monthly lower bounds models an extreme comonotonic stress test. And because AMFI reports monthly aggregates, intraday runs on the 15th of tax months must be managed via our operational floor and repo lines. Looking ahead, our production roadmap will integrate daily transaction feeds, joint copula interval estimation, and dynamic macro scenario engines. FINHYPE is robust, auditable, and ready for deployment."

### Source File & Evidence
* Limitations disclosure: [LIMITATIONS.md](file:///C:/Users/Alok/Desktop/FINHYPE/LIMITATIONS.md#L1-L67)
* System architecture: [ARCHITECTURE.md](file:///C:/Users/Alok/Desktop/FINHYPE/ARCHITECTURE.md#L115-L121)
* Release verification: [RELEASE_CHECKLIST.md](file:///C:/Users/Alok/Desktop/FINHYPE/RELEASE_CHECKLIST.md#L1-L107)

