# FINHYPE — Five-Minute Technical Pitch Script

**Project:** FINHYPE (Zeckathon 2026 · Problem Statement 3)  
**Role:** Lead Quantitative Developer & Financial Test Engineer  
**Target Duration:** Exactly 5 Minutes (approx. 650–700 spoken words at 130–140 WPM)  
**Tone:** Confident, precise, technically rigorous, candid on limitations, and grounded in production evidence  

---

### [0:00 – 0:45] The Problem: The Hidden Liquidity Whirlpool in Debt Mutual Funds

"Good morning, judges. In the Indian asset management industry, money market funds face a recurring operational paradox. 

Liquid Funds, managing over ₹6.25 lakh crore, and Overnight Funds, managing over ₹84,000 crore, are not passive investment vehicles. Corporate treasuries use them essentially as interest-bearing current accounts. Every quarter—in March, June, September, and December—corporations withdraw tens of thousands of crores to pay advance tax installments, only to reinvest those funds back into the system a few weeks later. 

In Overnight Funds, this dynamic is amplified to an extreme: monthly gross turnover exceeds **540% of total fund AUM**. That means every single month, over ₹4.2 lakh crore flows in and out of an ₹84,000 crore asset pool. 

If a fund manager underestimates this outflow, they face costly emergency borrowing in repo markets or forced liquidations. But if they hoard too much cash, fund yields drop, and institutional investors flee to competitors. Liquidity sizing is a daily, multi-thousand-crore balancing act."

---

### [0:45 – 1:30] The Quantitative Gap: Why Point Forecasting Alone Fails

"Most data science solutions attempt to solve this by training a forecasting model and predicting expected net flow. But in treasury risk management, a point forecast is fundamentally incomplete. 

Knowing that December will have an expected net outflow of ₹50,000 crore does not answer the treasurer's real question: *'How much liquid cash must I hold today to ensure our fund remains solvent under 90% or 97.5% severe market conditions?'* 

Furthermore, standard statistical intervals often rely on theoretical Gaussian bell curves that fail during market stress, or in-sample training residuals that hide model overfitting. 

FINHYPE bridges this gap. We built an end-to-end quantitative platform that forecasts 3-month net flows, estimates horizon-specific empirical uncertainty from genuine out-of-sample backtest errors, and converts those probabilistic bounds into an actionable, audit-defensible cash buffer."

---

### [0:30 – 2:30] The Architecture: Strict Temporal Isolation & 24 Rolling Origins

"Let's look under the hood. Our data foundation comprises 90 continuous monthly statements from the Association of Mutual Funds in India (AMFI) spanning April 2019 to September 2026. Every record is verified by an automated accounting invariant: gross mobilization minus gross repurchases must match net flow within one lakh rupees, or the SQLite transaction rolls back. 

We generate 53 domain-engineered features, including calendar tax cycles and shifted macroeconomic factors like the RBI repo rate. To guarantee zero future data leakage, every feature vector uses strictly lagged series, and all standardization transformers are fitted exclusively on past data. We verified this programmatically with an automated future-data mutation test across our 154 passing unit and integration tests.

To evaluate models, we executed a 24-origin expanding rolling backtest from July 2024 through June 2026 across four diverse model families: Seasonal-Naive, ETS, SARIMAX, and Ridge Regression. 

And crucially, our prediction intervals do not touch training residuals. They are calibrated directly from an expanding archive of historical out-of-sample forecast errors, admitting an error only after its target month has been fully realized in historical time."

---

### [2:30 – 3:45] The Findings: Empirical Model Hierarchy & Forward Projections

"Our empirical backtest benchmarks revealed critical structural insights:

In **Liquid Funds**, SARIMAX is the undisputed champion across all three horizons. At Month 1, it delivers an MAE of ₹27,618 crore, outperforming the Seasonal-Naive baseline by **+14.55% Skill Score**. Because it incorporates forward calendar regressors, SARIMAX correctly anticipates the cyclical reality ahead: a post-quarter liquidity surge of $+₹75,821\text{ Cr}$ in October 2026, followed by a severe corporate tax drainage of $-₹50,619\text{ Cr}$ in December.

In **Overnight Funds**, the empirical evidence taught us something unexpected: SARIMAX wins at Horizon 1 with an MAE of ₹13,941 crore (+7.62% Skill Score). But at Horizons 2 and 3, simple Seasonal-Naive persistence outperforms all complex models. Rather than forcing a single model everywhere, our architecture respects this empirical hierarchy."

---

### [3:45 – 4:30] The Decision: Peak Cumulative Deficit Buffer Sizing

"Now, how does FINHYPE turn these forecasts into an operational cash buffer? 

We developed a two-tier liquidity sizing formula: the recommended buffer is the maximum of an operational floor and the peak cumulative downside deficit over the planning horizon. 

$$\text{Recommended Buffer}_h = \max\left( \text{Base Operational Floor}, \; \text{Peak Cumulative Downside Deficit}_h \right)$$

For Liquid Funds in October 2026, the point forecast is positive, so the projected deficit is zero. The engine recommends exactly our 5% operational floor: **₹31,292 crore**. 

However, looking forward across the full 3-month horizon into December's advance-tax drain, our engine tracks cumulative downside shortfalls. To protect against the combined risk, the Moderate buffer expands to **₹75,073 crore (12% of AUM)**, while the Conservative buffer expands to **₹106,162 crore (almost 17% of AUM)**. 

Notice our non-monotonic rule: early liquidity shortfalls cannot be masked or erased by projected future inflows. The engine preserves maximum liquidity exposure."

---

### [4:30 – 5:00] Governance, Candour & Readiness

"Finally, we believe true quantitative excellence requires radical candour about limitations:

First, we do not claim guaranteed coverage. With 24 backtest origins, our nominal 80% and 95% levels are empirical calibration heuristics, not mathematical proofs against black swans. 

Second, our multi-month buffer is formally a conservative comonotonic stress test—it models an adverse scenario where worst-case shocks hit consecutively. In Overnight Funds, this comonotonic compounding of the severe November 2025 historical outlier yields a Conservative buffer exceeding 100% of AUM. We preserve this transparently rather than artificially capping it, because in a fund with 540% monthly turnover, gross liquidity shocks can indeed dwarf net assets. 

And third, because AMFI data is monthly, intraday cash runs on the 15th of tax months must be buffered via our base operational cushion and repo credit lines.

FINHYPE is complete, backed by 154 green tests, and ready for your live inspection on our Streamlit platform. Thank you, and we welcome your questions."

