# FINHYPE Phase 3: Exploratory Data Analysis & Empirical Findings

## Executive Summary
This report analyzes 90 months (April 2019 to September 2026) of official AMFI monthly data for **Indian Liquid Funds** and **Overnight Funds**. The target metric is monthly net fund flows (Funds Mobilised minus Redemptions in INR Crore).

Our empirical analysis demonstrates that fund flows in both categories are governed by powerful structural liquidity cycles:
1. **The Quarter-End Tax Drain**: Massive, statistically significant outflows occur in quarter-ending months (March, June, September, December), triggered by corporate advance tax obligations and bank balance-sheet management.
2. **The Post-Quarter Liquidity Rebound**: Immediate substantial inflows return in the subsequent months (April, July, October, January) as corporate cash pools replenish.
3. **Extreme Liquidity Turnover**: Overnight Funds turn over **5.44x** of their total AUM every single month, while Liquid Funds turn over **1.04x** of their AUM.
4. **Distinct Liquidity Roles**: While their net flows share a positive co-movement correlation of **+0.374**, their total AUMs are completely uncorrelated (**-0.026**), reflecting their distinct tenors (up to 91 days vs. 1 day).

---

## 1. Summary Statistics Comparison

The table below contrasts the distribution parameters between Liquid and Overnight mutual funds across the 90-month observation window:

| Metric | Liquid Fund | Overnight Fund | Interpretation |
| :--- | :--- | :--- | :--- |
| **Observation Months** | 90 | 90 | Full continuous historical coverage (Apr 2019 - Sep 2026) |
| **Mean Net Flow** | ₹463.51 Cr | ₹401.93 Cr | Long-run net flow is nearly balanced around zero |
| **Standard Deviation** | ₹64,307.47 Cr | ₹16,347.63 Cr | **Liquid Funds exhibit ~3.9x higher flow volatility** |
| **Median Net Flow** | ₹-679.41 Cr | ₹862.53 Cr | Reflects negative skew in Liquid due to tax drains |
| **Interquartile Range (IQR)** | ₹88,831.87 Cr | ₹16,220.48 Cr | Middle 50% dispersion |
| **Minimum Net Flow** | ₹-157,970.38 Cr | ₹-40,227.90 Cr | Maximum single-month liquidity drawdowns |
| **Maximum Net Flow** | ₹165,104.67 Cr | ₹46,280.05 Cr | Maximum single-month liquidity inflows |
| **Average AUM** | ₹445,842.80 Cr | ₹80,490.87 Cr | Liquid Fund AUM is ~5.5x larger than Overnight |
| **Avg Monthly Mobilisation** | ₹464,149.80 Cr | ₹422,188.24 Cr | Gross inflow volume |
| **Avg Monthly Redemption** | ₹463,686.29 Cr | ₹421,786.30 Cr | Gross outflow volume |
| **Monthly Turnover Ratio** | **1.04x of AUM** | **5.44x of AUM** | Overnight turns over >5x AUM per month |

---

## 2. The Quarter-End Phenomenon (Corporate Advance Tax)

In India, corporate advance tax installments fall on the 15th of June (15%), September (45%), December (75%), and March (100%). Additionally, banks and NBFCs curtail short-term lending at quarter-ends to optimize balance sheet metrics for regulatory disclosures.

The empirical divergence between Quarter-End months (Mar, Jun, Sep, Dec) and Non-Quarter-End months is stark:

| Category | Quarter-End Mean Net Flow | Non-Quarter-End Mean Net Flow | Net Quarterly Divergence |
| :--- | :--- | :--- | :--- |
| **Liquid Fund** | **₹-63,648.69 Cr** | **₹32,519.61 Cr** | **₹-96,168.30 Cr** |
| **Overnight Fund** | **₹-4,052.19 Cr** | **₹2,629.00 Cr** | **₹-6,681.18 Cr** |

### Key Takeaway for Forecasting:
A binary or categorical feature indicating `is_quarter_end` (or separate indicators for March vs. Jun/Sep/Dec) is mandatory. In Liquid Funds, quarter-ends produce an average drag of **~₹96,168 Crore** compared to non-quarter-end months.

---

## 3. Calendar Month Seasonality Profile

The table below breaks down average net flows by calendar month (January through December):

| Month | Advance Tax / Cycle | Liquid Fund Mean (Cr) | Overnight Fund Mean (Cr) |
| :--- | :--- | :--- | :--- |
| **January (1)** | Post-Q3 Rebound | ₹23,809.88 | ₹16,171.97 |
| **February (2)** | Mid-Quarter | ₹21,448.84 | ₹-4,485.54 |
| **March (3)** | **Fiscal Year-End Advance Tax** | **₹-93,848.66** | **₹-9,506.54** |
| **April (4)** | **Post-FY Rebound Inflow** | **₹84,824.61** | **₹13,492.73** |
| **May (5)** | Mid-Quarter | ₹11,000.57 | ₹-5,743.26 |
| **June (6)** | Q1 Advance Tax | ₹-48,343.86 | ₹-7,308.07 |
| **July (7)** | Post-Q1 Rebound Inflow | ₹45,495.47 | ₹9,940.25 |
| **August (8)** | Mid-Quarter | ₹13,293.92 | ₹-5,806.61 |
| **September (9)** | **Q2 Advance Tax (H1 Closing)** | **₹-77,957.57** | **₹3,548.02** |
| **October (10)** | Post-Q2 Rebound Inflow | ₹46,839.00 | ₹7,987.08 |
| **November (11)** | Mid-Quarter | ₹9,939.47 | ₹-10,719.98 |
| **December (12)** | Q3 Advance Tax | ₹-34,586.95 | ₹-3,562.76 |

---

## 4. Extreme Shocks and Outliers

Statistical outlier detection (|Z-score| >= 2.0) highlights the most extreme systemic events:

| Month | Category | Net Flow (INR Cr) | Z-Score | Classification | Drivers / Context |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2019-06 | Liquid Fund | ₹-152,431.65 | -2.38 | Extreme Outflow | Quarter-end tax / macro shock |
| 2019-09 | Liquid Fund | ₹-140,731.25 | -2.20 | Extreme Outflow | Quarter-end tax / macro shock |
| 2024-03 | Liquid Fund | ₹-157,970.38 | -2.46 | Extreme Outflow | Fiscal Year-end advance tax & book closing |
| 2025-03 | Liquid Fund | ₹-133,034.04 | -2.08 | Extreme Outflow | Fiscal Year-end advance tax & book closing |
| 2026-03 | Liquid Fund | ₹-134,987.64 | -2.11 | Extreme Outflow | Fiscal Year-end advance tax & book closing |
| 2026-04 | Liquid Fund | ₹+165,104.67 | +2.56 | Extreme Inflow | Post-FY corporate cash return |
| 2022-09 | Overnight Fund | ₹+33,128.33 | +2.00 | Extreme Inflow | Quarter-end tax / macro shock |
| 2025-11 | Overnight Fund | ₹-37,624.53 | -2.33 | Extreme Outflow | Quarter-end tax / macro shock |
| 2026-01 | Overnight Fund | ₹+46,280.05 | +2.81 | Extreme Inflow | Quarter-end tax / macro shock |
| 2026-03 | Overnight Fund | ₹-40,227.90 | -2.49 | Extreme Outflow | Fiscal Year-end advance tax & book closing |
| 2026-07 | Overnight Fund | ₹+40,412.55 | +2.45 | Extreme Inflow | Quarter-end tax / macro shock |

---

## 5. Cross-Category Relationship & Substitution Dynamics

1. **Net Flow Correlation (+0.374)**:
   - There is a positive, statistically significant co-movement between Liquid and Overnight fund flows.
   - This occurs because both categories respond in the same direction to macro liquidity drivers (systemic liquidity surges, RBI rate cuts, corporate tax windows).
2. **AUM Correlation (-0.026)**:
   - Despite flow co-movement, the total asset sizes do not share a common trend. Overnight fund AUM grew rapidly following the 2018-2019 NBFC liquidity crisis as conservative corporate treasuries sought minimal duration risk.
3. **Turnover & Cash Buffer Implications**:
   - Liquid funds hold 7-day minimum cash/sovereign buffers mandated by SEBI, but their monthly flows swing by upwards of ₹150,000 Crore.
   - Cash buffer sizing models must be strictly dynamic, scaling up dramatically ahead of March, June, September, and December.

---

## 6. Generated Visual Artifacts

The following self-contained, interactive Plotly visualizations were created and saved in `reports/figures/`:
1. `net_flows_time_series.html`: Full historical trajectory of monthly net flows with reference markers.
2. `gross_flows_comparison.html`: Inflows mobilized vs. redemptions demonstrating institutional churn.
3. `seasonality_calendar_month.html`: Grouped calendar seasonality by month (1 to 12).
4. `quarter_end_effect.html`: Box plots comparing quarter-end vs non-quarter-end distributions.
5. `outlier_analysis.html`: Extreme outlier points with annotated z-scores.
6. `category_correlation_scatter.html`: Liquid vs. Overnight scatter plot, OLS fit line, and rolling 12-month correlation.
