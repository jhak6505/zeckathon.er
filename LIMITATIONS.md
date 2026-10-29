# FINHYPE — Methodological Limitations & Model Governance Disclosures

**Document ID:** FINHYPE-LIMITATIONS-2026-10-29  
**Target:** Quantitative Reviewers, Risk Committees, and Evaluators  
**Scope:** Technical Limitations, Operational Assumptions, and Governance Safeguards  

---

## 1. Executive Summary of Limitations

While FINHYPE implements rigorous, leak-free quantitative forecasting and empirical out-of-sample error calibration across 90 historical months and 24 backtest origins, all financial models are mathematical abstractions of reality. 

Treasury risk managers must understand the specific structural and statistical boundaries of the system to prevent over-reliance on point estimates or nominal confidence intervals.

---

## 2. Detailed Methodological Limitations

### 2.1 Comonotonic Stress Deficit Aggregation vs. Joint Probability Intervals
* **The Methodology:** In the cash buffer engine, multi-month deficit aggregation sums monthly downside bounds:
  $$\text{Cumulative Downside}_k = \sum_{j=1}^k \hat{L}_{T+j}^{(\alpha)}$$
* **The Assumption:** This summation mathematically assumes **comonotonicity** (perfect positive tail dependence across consecutive months). It models an extreme scenario where a 90th or 97.5th percentile downside shock strikes in Month 1, followed immediately by another acute downside shock in Month 2, and another in Month 3.
* **Practical Implication:** 
  * The multi-month cash buffer is formally a **conservative comonotonic stress scenario**, not a calibrated joint 3-month probability interval.
  * In reality, institutional flow shocks often exhibit mean-reversion (e.g., massive corporate tax drainage in December is followed by substantial liquidity return in January).
  * Consequently, the multi-month buffer recommendation represents an advisory solvency cushion against compound systemic liquidity freezes, rather than an expected cash requirement.

### 2.2 Sample Size Granularity in Out-of-Sample Calibration ($N=24$)
* **The Evaluation Window:** The rolling backtest evaluates 24 historical monthly origins (July 2024 through June 2026).
* **Sample Discreteness:** With $N=24$ realized errors:
  * Each individual error observation represents **$4.17\%$** of the empirical cumulative distribution ($1/24$).
  * The 10th percentile ($q_{0.10}$) falls between the 2nd and 3rd worst historical errors.
  * The 2.5th percentile ($q_{0.025}$) relies on the single most extreme historical tail error.
* **Practical Implication:** 
  * Nominal confidence levels (80% and 95%) cannot be distinguished with high statistical power. A single additional historical outlier would shift empirical 95% coverage by over $4\%$.
  * Nominal confidence levels must be treated as empirical calibration heuristics, not as mathematically guaranteed coverage probabilities against unobserved market regimes.

### 2.3 Monthly Aggregation vs. Intraday Corporate Runs
* **Data Granularity:** AMFI publishes monthly aggregate net flow statements.
* **The Blind Spot:** In Indian corporate treasuries, advance-tax liquidity outflows do not occur evenly over the 30 days of the month; they are hyper-concentrated within a 48-to-72 hour window around the **15th of March, June, September, and December**.
* **Practical Implication:**
  * While the model accurately anticipates that December will experience severe net drainage (-₹50,619 Cr for Liquid Funds), it cannot project intraday redemption spikes on December 14th or 15th.
  * Fund managers must rely on the **Base Operational Floor** ($b_{\text{base}} \times \text{AUM}$, default 5% for Liquid, 2.5% for Overnight) and intraday liquidity facilities to absorb intra-month settlement frictions.

### 2.4 Sensitivity to Extreme Historical Regime Shifts (November 2025 Outlier)
* **The Event:** In November 2025, AMFI recorded an unprecedented net outflow of **-₹37,624.53 Cr** in Overnight Funds (gross repurchases exceeded ₹5.28 lakh Cr on gross turnover exceeding 500% of fund AUM).
* **The Model Response:**
  * The Seasonal-Naive model repeats 12-month-old observations, directly propagating this -₹37,624 Cr projection into November 2026.
  * When compounded with empirical error percentiles and comonotonic deficit aggregation, the 3-month Conservative recommendation reaches **₹118,049.89 Cr (140.48% of current AUM)** under the Single-Model baseline and **₹129,620.28 Cr (154.25% of AUM)** under the Step-Wise Stitched trajectory.
* **Governance Principle:**
  * These figures were intentionally preserved without artificial capping or mathematical smoothing.
  * A buffer exceeding 100% of fund AUM is mathematically coherent in funds where gross monthly turnover exceeds $500\%$ of total assets, reflecting extreme gross redemption churn rather than a defect in the algorithm.
  * However, fund treasuries in practice would utilize sovereign repo lines, RBI standing deposit facilities (SDF), and sponsor support rather than holding $>100\%$ cash in an overnight fund.

### 2.5 Exogenous Macroeconomic Projections Under Constant Policy Rates
* **Forward Macro Assumptions:** Multi-step forward forecasting assumes constant forward policy rates ($\Delta \text{Repo}_{T+h} = 0$) and neutral equity sentiment ($\text{Return}_{T+h} = 0$).
* **Practical Implication:**
  * If the Reserve Bank of India executes an unannounced inter-meeting repo rate hike or sudden cash reserve ratio (CRR) adjustment, yield curves will shift abruptly, inducing unexpected institutional reallocation between Overnight and Liquid funds that cannot be anticipated by static macro projections.

---

## 3. Recommended Treasury Deployment Safeguards

1. **Dual Horizon Review:** Treasuries should review both the **1-Month Standalone Recommendation** (governed by SARIMAX for immediate monthly operational allocation) and the **3-Month Multi-Period Trajectory** (for quarterly board risk reporting).
2. **Dynamic Base Floor Customization:** Use the dashboard slider to adjust the Base Operational Floor percentage depending on fund-specific investor concentration (e.g., if top 10 institutional investors hold >30% of units, elevate base floor to 7–8%).
3. **Routine Out-of-Sample Recalibration:** At the close of each calendar month, ingest newly released AMFI statements into `data/finhype.db` and re-run `python run_pipeline.py` to refresh backtest error archives.

