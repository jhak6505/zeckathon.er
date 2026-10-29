# FINHYPE Phase 5: Cash Buffer Recommendation Engine Design Note
**Treasury Liquidity Buffer Sizing under Net Flow Uncertainty**
*Zeckathon 2026 – Problem Statement 3*

---

## 1. The Exact Cash-Buffer Formula

In open-ended Indian mutual funds (Liquid and Overnight), cash buffer sizing must satisfy two distinct financial requirements:
1. **Structural Net Outflow Absorption**: Capital needed to honor net redemptions over the planning horizon without forced liquidation of longer-dated assets or incurring punitive bid-ask spreads.
2. **Operational Liquidity Floor (Intra-Month Churn Cushion)**: Minimum liquidity floor required to manage day-to-day transaction friction, gross mobilisations, and redemption mismatches before month-end net positions settle.

### Mathematical Formulation

Let:
* $h \in \{1, 2, 3\}$ be the planning horizon in months.
* $\hat{Y}_{T+k}$ be the point forecast for month $T+k$ (in INR Crore), where $\hat{Y} < 0$ denotes a net outflow.
* $\hat{L}_{T+k}^{(\alpha)}$ be the lower bound of the $(1-\alpha)$ prediction interval for month $T+k$ (e.g. $\alpha=0.20$ for 80% confidence, $\alpha=0.05$ for 95% confidence).
* $\text{AUM}_T$ be the latest observed month-end Asset Under Management (INR Crore).
* $b_{\text{base}} \in [0, 1]$ be the **user-configurable base operational liquidity percentage** (default: 5.0% for Liquid Funds, 2.5% for Overnight Funds; SEBI statutory minimum liquid asset requirement is 20% for Liquid Funds, but statutory holdings include sovereign T-Bills and repos).

The **Recommended Cash Buffer** for horizon $h$ is defined as:

$$\text{Recommended Buffer}_h = \max\left( \text{Base Operational Buffer}, \; \text{Peak Cumulative Downside Deficit}_h \right)$$

where:
$$\text{Base Operational Buffer} = b_{\text{base}} \times \text{AUM}_T$$
$$\text{Cumulative Downside Deficit}_k = \max\left(0, -\sum_{j=1}^k \hat{L}_{T+j}^{(\alpha)}\right), \quad k \in \{1, \dots, h\}$$
$$\text{Peak Cumulative Downside Deficit}_h = \max_{k \in \{1, \dots, h\}} \text{Cumulative Downside Deficit}_k$$

---

## 2. Multi-Month Negative Flow Aggregation

A common error in liquidity planning is taking a simple net sum over $h$ months. For example, if a fund experiences:
* Month 1: $-₹60,000$ Cr outflow
* Month 2: $+₹80,000$ Cr inflow

The net 2-month balance is $+₹20,000$ Cr, but the fund manager would face insolvency in Month 1 if only $+₹20,000$ Cr were buffered. 

Conversely, treating each month's buffer as independently additive ($₹60,000 + 0 = ₹60,000$ Cr) fails if Month 2 also experiences a negative outflow (e.g. Month 1: $-₹50,000$ Cr, Month 2: $-₹40,000$ Cr, requiring a cumulative cash pool of $₹90,000$ Cr).

### Aggregation Rule: Peak Cumulative Deficit Trajectory
We track the running cumulative net downside balance:
$$S_k = \sum_{j=1}^k \hat{L}_{T+j}^{(\alpha)}, \quad k=1, \dots, h$$
The cumulative deficit at month $k$ is:
$$D_k = \max(0, -S_k)$$
The aggregate requirement across the multi-month horizon is the **peak cumulative deficit**:
$$\text{Deficit}_h = \max(D_1, D_2, \dots, D_h)$$

This aggregation rule:
1. Guarantees that intra-horizon liquidity depletion in early months is fully funded.
2. Prevents future positive inflows from erasing the requirement of an immediate, acute drawdown.
3. Fully accounts for compound consecutive outflows (such as consecutive corporate tax drainage across quarterly transitions).

### Statistical Nature of Multi-Month Aggregation: Comonotonic Stress Scenario
It is vital to distinguish between a **statistically calibrated multi-month prediction interval** and the **comonotonic scenario calculation** performed here:
* Quantiles are **not subadditive or linear** in general ($q_\alpha(X_1 + X_2) \neq q_\alpha(X_1) + q_\alpha(X_2)$). Summing marginal quantiles equals the quantile of the sum only under **comonotonicity** (perfect positive rank dependence $\rho = 1$).
* By summing marginal lower bounds $\sum_{j=1}^k \hat{L}_{T+j}^{(\alpha)}$, the engine models an extreme scenario where adverse tail shocks strike in *every single month consecutively*.
* Consequently, the joint probability of experiencing consecutive 10th-percentile outcomes across 3 months is well below 10% (under independence, $0.10^3 = 0.001 = 0.1\%$).
* **Methodological Classification**: The multi-month cumulative deficit is formally classified as a **conservative stress-test scenario**, rather than a statistically calibrated multi-month $(1-\alpha)$ joint prediction interval.

---

## 3. How Prediction Intervals Affect the Buffer

Prediction intervals directly parameterize liquidity uncertainty:
* The point forecast $\hat{Y}_{T+k}$ provides the expected central scenario.
* Sizing a cash buffer strictly to the point forecast $\hat{Y}_{T+k}$ implies an approximate **50% probability of under-buffering** if forecast errors are symmetric!
* The **lower bound $\hat{L}_{T+k}^{(\alpha)}$** is derived from a two-sided $(1-\alpha)$ prediction interval $[\hat{L}_{T+k}^{(\alpha)}, \hat{U}_{T+k}^{(\alpha)}]$ with empirical error quantiles:
  $$\hat{L}_{T+k}^{(\alpha)} = \hat{Y}_{T+k} + \text{Quantile}_{\alpha/2}\left(\{e_{\tau, h}\}\right)$$
  As a one-sided downside floor, this provides **$(1 - \alpha/2)$ one-sided downside coverage**:
  $$\mathbb{P}\left( Y_{T+k} \ge \hat{L}_{T+k}^{(\alpha)} \;\middle|\; \mathcal{F}_T \right) \approx 1 - \frac{\alpha}{2}$$
  - For **Moderate Profile ($\alpha = 0.20$)**: Uses the 10th percentile error ($\alpha/2 = 0.10$), yielding **90.0% one-sided downside coverage** (10% downside tail risk).
  - For **Conservative Profile ($\alpha = 0.05$)**: Uses the 2.5th percentile error ($\alpha/2 = 0.025$), yielding **97.5% one-sided downside coverage** (2.5% downside tail risk).
* The **uncertainty cushion** (risk premium) added to the expected flow is:
  $$\text{Safety Margin}_k = \hat{Y}_{T+k} - \hat{L}_{T+k}^{(\alpha)} \ge 0$$
* If forecast uncertainty widens (e.g. during volatile fiscal year-end periods or for longer horizons $h=3$), $\hat{L}_{T+k}^{(\alpha)}$ becomes more negative, automatically expanding the required buffer.

---

## 4. How Risk Tolerance Changes the Recommendation

Users configure risk tolerance via a discrete confidence selector or risk profile:
1. **Moderate Risk Tolerance (80% Confidence, $\alpha = 0.20$)**:
   * Uses $\hat{L}^{(0.20)}$ derived from historical 10th percentile error bounds.
   * Expected shortfall probability is 10% on the downside.
   * Suitable for normal operating months where funds have access to collateralized overnight borrowing (TREPS) to manage tail shocks.
2. **Conservative Risk Tolerance (95% Confidence, $\alpha = 0.05$)**:
   * Uses $\hat{L}^{(0.05)}$ derived from historical 2.5th percentile error bounds.
   * Expected shortfall probability is 2.5% on the downside.
   * Expands the buffer significantly ahead of March fiscal year-ends to prevent fire-selling commercial papers during market-wide liquidity crunches.
3. **Aggressive / Cost-Optimized (50% / Expected Flow)**:
   * Uses $\hat{Y}_{T+k}$ directly with operational floor.
   * Minimizes cash drag (cash yields are lower than short-term debt paper), but accepts higher refinancing risk.

All risk preferences and operational floor parameters are exposed as **explicit, user-configurable assumptions** in the dashboard.

---

## 5. What the Historical Backtest Can and Cannot Validate

### What the Backtest CAN Validate
* **Empirical Coverage**: Confirms whether historical actual flows remained above the recommended downside bound $\hat{L}^{(\alpha)}$ in approximately $(1-\alpha)\%$ of evaluation origins over the 24-month backtest window.
* **Model Relative Sharpness**: Quantifies which model provides the tightest required buffer (minimizing cash drag) while maintaining nominal coverage.
* **Quarter-End Anticipation**: Validates that SARIMAX dynamically expands the buffer ahead of March, June, September, and December tax cycles.

### What the Backtest CANNOT Validate
* **Systemic Black-Swan Shocks**: Cannot guarantee solvency during unprecedented external credit events (e.g. 2008 global financial crisis, 2018 IL&FS default, March 2020 pandemic lockdown).
* **Intra-Month Daily Cash Runs**: AMFI reports provide monthly aggregate figures. Daily liquidity spikes (e.g. large redemptions between the 15th and 20th of tax months) are not captured in monthly net flow totals.
* **Idiosyncratic Investor Concentrations**: A single institutional client withdrawing large sums from a mid-sized fund cannot be predicted by market-wide macroeconomic models.

---

## 6. Forward Baseline Recommendations & Outlier Sensitivity (Origin 2026-09)

The forward recommendations evaluated from the latest historical origin (September 2026) for October, November, and December 2026 are summarized below:

### Liquid Fund (AUM: ₹625,847.01 Cr | Base Floor: 5.0% = ₹31,292.35 Cr)
* **Horizon 1 (Oct 2026, `SARIMAX`)**: Point forecast $+₹75,820.52 \text{ Cr}$ (post-quarter rebound). Downside deficit is ₹0.00 Cr. **Recommended Buffer: ₹31,292.35 Cr (5.00% of AUM)**.
* **Horizon 2 (Oct–Nov 2026, `SARIMAX`)**: Cumulative point $+₹66,840.54 \text{ Cr}$. Moderate deficit ₹0.00 Cr, Conservative deficit ₹11,656.06 Cr. **Recommended Buffer: ₹31,292.35 Cr (5.00% of AUM)** governed by base floor.
* **Horizon 3 (Oct–Dec 2026, `SARIMAX`)**: December Q3 corporate tax drainage (Month 3 point forecast $-₹50,618.62 \text{ Cr}$, lower bound $-₹91,294.66 \text{ Cr}$). Cumulative downside triggers dynamic buffer expansion:
  - **Moderate (80% 2-Sided / 90% Downside)**: Peak deficit **₹75,072.74 Cr (12.00% of AUM)**.
  - **Conservative (95% 2-Sided / 97.5% Downside)**: Peak deficit **₹106,161.75 Cr (16.96% of AUM)**.

### Overnight Fund (AUM: ₹84,032.57 Cr | Base Floor: 2.5% = ₹2,100.81 Cr)
* **Horizon 1 (Oct 2026, `SARIMAX`)**: Point forecast $+₹16,981.99 \text{ Cr}$. Downside lower bound $-₹10,366.04 \text{ Cr}$.
  - **Moderate**: **₹10,366.04 Cr (12.34% of AUM)**.
  - **Conservative**: **₹17,606.86 Cr (20.95% of AUM)**.
* **Horizon 2 (Oct–Nov 2026, `Seasonal-Naive`)**:
  - **Moderate**: **₹53,023.40 Cr (63.10% of AUM)**.
  - **Conservative**: **₹80,982.57 Cr (96.37% of AUM)**.
* **Horizon 3 (Oct–Dec 2026, `Seasonal-Naive`)**:
  - **Moderate**: **₹74,130.35 Cr (88.22% of AUM)**.
  - **Conservative**: **₹118,049.89 Cr (140.48% of AUM)**.

### Sensitivity to the November 2025 Historical Outlier
The multi-month Overnight Fund cash buffer recommendation (₹74,130.35 Cr under Moderate, ₹118,049.89 Cr under Conservative) is highly sensitive to the empirical November 2025 net outflow of **-₹37,624.53 Cr** recorded in the AMFI dataset:
1. **Model Persistence**: Seasonal-Naive was selected for Overnight Horizons 2 and 3 because it yielded the lowest MAE and highest empirical coverage in backtesting. Consequently, it replicates the November 2025 record outflow for November 2026.
2. **Quantile Stacking**: Combining the $-₹37,624.53 \text{ Cr}$ point forecast with the empirical 10th-percentile error ($-₹21,542.78 \text{ Cr}$) creates a severe Month 2 downside projection of $-₹59,167.31 \text{ Cr}$.
3. **Comonotonic Compound Conservatism**: Summing the downside bounds of Month 1 ($+₹6,143.91 \text{ Cr}$), Month 2 ($-₹59,167.31 \text{ Cr}$), and Month 3 ($-₹21,106.95 \text{ Cr}$) produces a cumulative comonotonic downside shortfall of ₹74,130.35 Cr.
4. **Preservation of Analytical Integrity**: These calculations and outputs are strictly preserved without artificial dampening or outlier suppression, ensuring full transparency regarding how historical empirical extremes influence treasury liquidity requirements under stress.

---

*This design note provides the formal basis for `app/services/cash_buffer.py` and the interactive Streamlit recommendation dashboard.*

