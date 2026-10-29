# FINHYPE Phase 4: Revised Forecasting System Design Document
**Mutual Fund Flow Forecasting & Horizon-Based Liquidity Evaluation**
*Zeckathon 2026 – Problem Statement 3*

---

## Executive Summary of Design Revisions

In accordance with Phase 4 architecture requirements, this revised design document incorporates the following structural changes:
1. **Model Suite Alignment**: **Ridge Regression** is established as the primary regularized machine learning model. **LightGBM** is designated as an optional, secondary exploratory model with strict low-complexity constraints. Deep learning remains explicitly excluded.
2. **Strict Exogenous Protocol**: Future macroeconomic values (RBI repo rate decisions, Nifty 50 returns) are strictly prohibited from future horizon steps. SARIMAX regressors rely on deterministic calendar indicators and clearly documented zero-change/neutral forward macro assumptions.
3. **Out-of-Sample Prediction Intervals**: In-sample training residuals are strictly prohibited for interval calibration. Prediction intervals are calibrated using **horizon-specific, historical out-of-sample forecast errors** available strictly prior to each forecast origin.
4. **Origin-Specific Metric Scaling**: The $\epsilon$ floor for the MAPE denominator is computed dynamically at each forecast origin using only training targets available at that origin. Limitations of percentage errors for zero-crossing series are documented.
5. **Overlapping Multi-Step Dependency**: The multi-step forecast error autocorrelation ($\text{MA}(h-1)$ dependency) across overlapping rolling origins is formally recognized in evaluation.
6. **Benchmark Relativity**: Every model is evaluated both in absolute terms and relative to the Seasonal-Naive baseline across all horizons.

---

## 1. Problem Formulation & Feature-Availability Architecture

### 1.1 Target Variable & Forecasting Horizons
* **Target Variable**: Monthly net fund flow:
  $$\text{Net Flow}_t = \text{Funds Mobilised}_t - \text{Redemptions}_t \quad (\text{in INR Crore})$$
* **Forecast Horizons**: Multi-step trajectory of **$h \in \{1, 2, 3\}$ months ahead**.
  * At forecast origin $T$, the system forecasts $Y_{T+1}$, $Y_{T+2}$, and $Y_{T+3}$.
* **Decoupled Execution**:
  * Liquid Funds and Overnight Funds are trained and evaluated as **separate, decoupled models**.
  * Scale and turnover characteristics differ by multiple orders of magnitude (Liquid Fund net flow $\sigma \approx ₹64,307$ Cr with $1.04\times$ turnover vs. Overnight Fund $\sigma \approx ₹16,348$ Cr with $5.44\times$ turnover; AUM correlation is $-0.026$).
  * Cross-category liquidity spillover is incorporated safely via strictly lagged peer features (`peer_net_inflow_lag_1`, `peer_aum_lag_1`).

### 1.2 Information Set at Forecast Origin $T$ ($\mathcal{F}_T$)
At forecast origin $T$ (representing the close of month $T$), the forecaster has access to:
1. **Target History**: $\{Y_t\}_{t=1}^T$ for both fund categories.
2. **Fund Fundamentals**: Gross mobilisations, redemptions, month-end AUM, and average AUM up to month $T$.
3. **Macroeconomic Indicators**: RBI Policy Repo Rate (% p.a.), month-over-month repo rate change (bps), and Nifty 50 closing index and returns up to month $T$.
4. **Deterministic Future Calendar Features**: Known in advance for future months $T+1, T+2, T+3$ with mathematical certainty:
   * `calendar_month`, `quarter`, `days_in_month`
   * `is_advance_tax_month` (1 for March, June, September, December; 0 otherwise)
   * `is_quarter_end` (1 for Q1/Q2/Q3/Q4 closing months)
   * `is_fy_end` (1 for March)
   * `is_post_quarter_month` (1 for April, July, October, January)
   * Cyclical encodings: $\sin(2\pi m / 12)$, $\cos(2\pi m / 12)$

### 1.3 Strict Feature Exclusion & Anti-Leakage Rules
To ensure zero forward-looking leakage:
* **Excluded**: Any contemporaneous flow or AUM values from $T+1, T+2, T+3$ (`funds_mobilised_{T+h}`, `redemption_{T+h}`, `aum_{T+h}`).
* **Excluded**: Realized future macroeconomic indicators (`repo_rate_{T+h}`, `nifty_return_{T+h}`).
* **Excluded**: Global target scalers or global imputers computed across the entire 90-month history.

---

## 2. Proposed Model Suite

The four models span from parsimonious baselines to regularized linear and tree methods:

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                              FINHYPE Model Suite                                  │
├─────────────────────┬───────────────────┬───────────────────┬─────────────────────┤
│ 1. Seasonal-Naive   │ 2. ETS            │ 3. SARIMAX        │ 4. Ridge Regression │
│ (Baseline Anchor)   │ (Smooth Season)   │ (Exogenous Flags) │ (Primary Reg. ML)   │
└─────────────────────┴───────────────────┴───────────────────┴─────────────────────┘
                                          │
                                          ▼ [Optional / Secondary]
                                    5. LightGBM (Constrained Depth)
```

### 2.1 Model 1: Seasonal-Naive Baseline (S-Naive)
* **Mathematical Specification**:
  $$\hat{Y}_{T+h} = Y_{T+h-12}$$
  *(e.g., the forecast for March 2026 is the actual net flow of March 2025).*
* **Role**: Primary domain benchmark. Captures the annual advance tax calendar (March FY-end drain, September H1 closing, April cash rebound). All candidate models are judged against S-Naive.

### 2.2 Model 2: Classical Statistical Model (ETS / Holt-Winters)
* **Mathematical Specification**: Automated Exponential Smoothing with additive error, additive damped trend, and additive seasonal components: **ETS(A, Ad, A)** with seasonal frequency $m=12$.
* **Rationale**:
  * Net flows cross zero and are frequently negative, ruling out multiplicative formulations ($\text{ETS}(M, \cdot, M)$).
  * Smooths local level shifts while maintaining annual seasonality without requiring large sample sizes.

### 2.3 Model 3: Econometric Transfer Function (SARIMAX)
* **Mathematical Specification**:
  $$\Phi_P(B^{12})\phi_p(B)(1 - B)^d(1 - B^{12})^D Y_t = \beta' X_t + \Theta_Q(B^{12})\theta_q(B)\epsilon_t$$
* **Regressors ($X_t$)**:
  * Deterministic calendar flags: `is_advance_tax_month`, `is_fy_end`, `is_post_quarter_month`.
  * Lagged macro indicators known at origin $T$.
* **Rationale**: Integrates seasonal autoregressive-moving average dynamics with corporate tax calendar shocks.

### 2.4 Model 4: Ridge Regression (Primary Regularized ML Model)
* **Mathematical Specification**: Direct multi-step linear regression with $L_2$ Tikhonov regularization:
  $$\hat{Y}_{T+h} = \mathbf{w}_h' \mathbf{x}_T + b_h, \quad \min_{\mathbf{w}_h, b_h} \sum_{t=1}^{T-h} \left(Y_{t+h} - (\mathbf{w}_h' \mathbf{x}_t + b_h)\right)^2 + \lambda_h \|\mathbf{w}_h\|_2^2$$
* **Rationale & Sample Size Justification**:
  * Training sample size at each origin is $N \in [51, 74]$ post-warmup.
  * With ~15-20 candidate features (calendar dummies, lags, rolling stats, churn, macro), unregularized OLS or high-capacity models overfit.
  * Ridge regression provides low variance, shrinks collinear lag coefficients stably, and prevents partition instability.
  * Regularization parameter $\lambda_h$ is tuned via expanding time-series cross-validation strictly on data prior to origin $T$.

### 2.5 Model 5: LightGBM (Optional / Secondary Exploratory Model)
* **Specification**: Direct multi-step gradient boosted trees ($h=1, 2, 3$).
* **Complexity Constraints**:
  * `max_depth = 2` (shallow decision stumps/pairs only)
  * `num_leaves = 4`
  * `min_child_samples = 8`
  * `learning_rate = 0.03`, `n_estimators = 50`, `colsample_bytree = 0.8`
* **Role**: Evaluated strictly as a secondary comparison to determine whether non-linear feature interactions provide measurable gains over Ridge regression on this sample size.
* **Exclusion of Deep Learning**: Deep recurrent models (LSTMs, GRUs) and Transformers (TFT, N-BEATS) require thousands of observations and are firmly excluded to avoid overfitting.

---

## 3. Protocol for Future Exogenous Variables & Macro Assumptions

In multi-step forecasting ($h=1, 2, 3$), using actual realized future values of macroeconomic indicators constitutes data leakage.

### 3.1 Handling SARIMAX Regressors
SARIMAX models require future values of exogenous regressors for horizons $T+1, T+2, T+3$. The following protocol applies:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Exogenous Regressor Treatment at Origin T                │
├───────────────────────────────┬─────────────────────────────────────────────┤
│ Regressor Type                │ Horizon Value Treatment (h = 1, 2, 3)       │
├───────────────────────────────┼─────────────────────────────────────────────┤
│ 1. Calendar / Tax Indicators  │ Deterministic truth for T+h (no leakage)    │
│    (is_quarter_end, is_fy_end)│                                             │
│ 2. RBI Policy Repo Rate       │ Policy Rate Persistence Assumption:         │
│                               │ Repo_{T+h} = Repo_T  ==>  ΔRepo_{T+h} = 0   │
│ 3. Nifty 50 Equity Return     │ Neutral Market Assumption:                  │
│                               │ NiftyReturn_{T+h} = 0 (or historical mean)  │
└───────────────────────────────┴─────────────────────────────────────────────┘
```

1. **Deterministic Calendar Variables**:
   * `is_advance_tax_month`, `is_quarter_end`, `is_fy_end`, `is_post_quarter_month`.
   * Known with certainty for all future horizons. No forward assumptions required.
2. **RBI Policy Repo Rate**:
   * **Forward Assumption**: Constant policy rate prevailing at origin $T$ ($\Delta \text{Repo}_{T+h} = 0$).
   * **Justification**: In the absence of an MPC meeting announcement, the rational expectation of future short-term policy changes is zero unannounced change.
3. **Nifty 50 Equity Return**:
   * **Forward Assumption**: Neutral zero-drift return ($\text{NiftyReturn}_{T+h} = 0$) or expanding historical training-mean return.

### 3.2 Direct ML Formulation (Ridge / LightGBM)
Direct ML models bypass future macro assumptions entirely by mapping:
$$\hat{Y}_{T+h} = f_h\left( \mathbf{x}_T^{\text{macro}}, \mathbf{x}_T^{\text{lags}}, \mathbf{x}_{T+h}^{\text{calendar}} \right)$$
where $\mathbf{x}_T^{\text{macro}}$ contains strictly observed macroeconomic state variables at origin $T$ (`repo_rate_lag_1`, `repo_rate_change_bps_lag_1`, `nifty_return_pct_lag_1`).

---

## 4. Prediction Intervals & Out-of-Sample Calibration

### 4.1 Strict Prohibition of In-Sample Residuals
* **Rule**: **Under no circumstances will in-sample training residuals be used to construct prediction intervals.**
* **Reason**: In-sample residuals $e_t^{\text{in-sample}} = Y_t - \hat{Y}_t^{\text{fit}}$ suffer from severe optimism bias and fail to capture multi-step forecast error growth ($\sigma^2(h) > \sigma^2(1)$).

### 4.2 Horizon-Specific Out-of-Sample Calibration Framework
For every model and each horizon $h \in \{1, 2, 3\}$, prediction intervals are constructed from **out-of-sample forecast errors accumulated strictly prior to origin $T$**:

1. **Expanding Out-of-Sample Error Archive**:
   At each origin $T$, the backtest maintains the historical archive of genuine out-of-sample errors:
   $$e_{\tau, h}^{\text{OOS}} = Y_{\tau+h} - \hat{Y}_{\tau+h \mid \tau}, \quad \text{for origins } \tau \le T - h$$
   *(where $\hat{Y}_{\tau+h \mid \tau}$ was the out-of-sample forecast produced at earlier origin $\tau$).*
2. **Warmup Cross-Validation Initialization**:
   For early origins before a sufficient number of OOS errors accumulate, a temporal expanding-block cross-validation over the training set $[1, T]$ generates initial pseudo-OOS residual sets $\{e_{i, h}^{\text{CV}}\}_{i=1}^{M_T}$.
3. **Empirical Quantile Prediction Intervals**:
   From the horizon-specific out-of-sample error distribution $\mathcal{E}_{T, h}$, calculate empirical quantiles:
   $$\hat{q}_{\alpha/2}(h) = \text{Quantile}_{\alpha/2}(\mathcal{E}_{T, h}), \quad \hat{q}_{1 - \alpha/2}(h) = \text{Quantile}_{1 - \alpha/2}(\mathcal{E}_{T, h})$$
   The prediction interval for $\hat{Y}_{T+h}$ is:
   $$\text{PI}_{1-\alpha}(T+h) = \left[ \hat{Y}_{T+h} + \hat{q}_{\alpha/2}(h), \quad \hat{Y}_{T+h} + \hat{q}_{1 - \alpha/2}(h) \right]$$
4. **Parametric Scaling for ETS / SARIMAX**:
   For parametric state-space models, the analytical multi-step error variance $\sigma_h^2 = \text{Var}(e_{T+h} \mid \mathcal{F}_T)$ provides the base shape, which is scaled by an empirical calibration factor $\gamma_{T, h}^{(\alpha)}$ derived from historical out-of-sample coverage up to origin $T$:
   $$\text{PI}_{1-\alpha}(T+h) = \hat{Y}_{T+h} \pm \gamma_{T, h}^{(\alpha)} \cdot z_{\alpha/2} \cdot \sigma_h$$

### 4.3 Statistical Limitations of 95% Coverage on 24 Origins
* **Sample Size**: Evaluating across $K = 24$ origins provides 24 test points per horizon.
* **Resolution Limit**: Each individual test observation constitutes $\frac{1}{24} \approx 4.17\%$ of empirical coverage.
* **Binomial Test Power**:
  * For nominal 95% coverage, the expected number of miscovered points is $0.05 \times 24 = 1.2$ observations.
  * If 1 point is missed: Coverage = $23/24 = 95.8\%$.
  * If 2 points are missed: Coverage = $22/24 = 91.7\%$.
  * If 3 points are missed: Coverage = $21/24 = 87.5\%$.
  * The exact 95% Clopper-Pearson confidence interval for an observed $23/24$ ($95.8\%$) spans **$[78.9\%, 99.9\%]$**.
* **Implication**: Empirical 95% coverage cannot be distinguished from 85% or 99% with high statistical confidence over 24 points. In contrast, **80% coverage** (expected $4.8$ misses) provides greater statistical power and tighter confidence bounds. Both 80% and 95% intervals will be reported with this sample size limitation clearly documented.

---

## 5. Rolling-Origin Backtesting Architecture

### 5.1 Origins & Window Construction
* **Evaluation Origins**: **24 monthly origins** spanning **July 2024 through June 2026** (`2024-07` to `2026-06`).
* **Complete Horizon Verification**:
  * At Origin 1 (`2024-07`): Forecasts `2024-08` ($h=1$), `2024-09` ($h=2$), `2024-10` ($h=3$).
  * At Origin 24 (`2026-06`): Forecasts `2026-07` ($h=1$), `2026-08` ($h=2$), `2026-09` ($h=3$).
  * All 72 horizon forecasts per model per category have actual ground truth in AMFI records.
* **Expanding Training Window**:
  * Training start is fixed at `2019-04`.
  * Training length expands from $63$ months at Origin 1 to $86$ months at Origin 24.
  * Preserves multi-year seasonal memory (critical for observing multiple March tax cycles).

### 5.2 Multi-Step Overlapping Dependency
* **Serial Correlation in Horizon Errors**:
  * For $h=2$ and $h=3$, forecast windows across consecutive origins overlap in calendar time:
    * Origin $T$ forecasts target month $T+2$.
    * Origin $T+1$ forecasts target month $T+2$ as its $h=1$ step.
  * Multi-step forecast errors inherently follow an **$\text{MA}(h-1)$ process**.
  * Therefore, the 24 evaluation errors are **not independent and identically distributed (non-i.i.d.)**.
  * Any hypothesis testing between models (e.g. Diebold-Mariano test) must incorporate a Harvey-Leybourne-Newbold or Newey-West lag adjustment with bandwidth $h-1$.

---

## 6. Evaluation Metrics Framework

### 6.1 Metric Formulations & Explanations

| Metric | Mathematical Formula | Handling of Zero/Negative Flows & Interpretation |
| :--- | :--- | :--- |
| **MAE** | $\frac{1}{K}\sum_{k=1}^K \|Y_{T_k+h} - \hat{Y}_{T_k+h}\|$ | **Primary scale-dependent metric** in INR Crore. Directly interpretable for liquidity sizing. |
| **RMSE** | $\sqrt{\frac{1}{K}\sum_{k=1}^K (Y_{T_k+h} - \hat{Y}_{T_k+h})^2}$ | Heavily penalizes extreme forecast misses during volatile quarter-ends. |
| **WAPE** | $\frac{\sum_{k=1}^K \|Y_{T_k+h} - \hat{Y}_{T_k+h}\|}{\sum_{k=1}^K \|Y_{T_k+h}\|}$ | **Scale-independent volume-weighted error**. Denominator never divides by individual zero/near-zero months; completely stable. |
| **MASE** | $\frac{\text{MAE}_h}{\frac{1}{T-12}\sum_{t=13}^T \|Y_t - Y_{t-12}\|}$ | Evaluates accuracy relative to in-sample seasonal naive persistence. **$\text{MASE} < 1.0$ indicates model outperforms seasonal persistence**. Scaling denominator computed strictly using training data up to origin $T$. |
| **MAPE$_\epsilon$** | $\frac{100\%}{K}\sum_{k=1}^K \frac{\|Y_{T_k+h} - \hat{Y}_{T_k+h}\|}{\max(\|Y_{T_k+h}\|, \epsilon_{T_k})}$ | Reported for problem requirement compliance. **$\epsilon_{T_k}$ floor is computed dynamically at each origin $T_k$** as the 10th percentile of absolute training targets: $\epsilon_T = \text{P}_{10}(\{\|Y_t\|\}_{t=1}^T)$. |
| **Pinball Loss** | $\frac{1}{K}\sum_{k=1}^K \max(\tau(y - \hat{q}), (1-\tau)(\hat{q} - y))$ | Evaluated at $\tau \in \{0.025, 0.10, 0.90, 0.975\}$. Measures quantile forecast fidelity for cash buffer sizing. |
| **Coverage$_\alpha$** | $\frac{1}{K}\sum_{k=1}^K \mathbb{I}(Y_{T_k+h} \in [\hat{L}, \hat{U}])$ | Percentage of actuals inside interval (nominal targets 80% and 95%). |
| **MIW$_\alpha$** | $\frac{1}{K}\sum_{k=1}^K (\hat{U}_{T_k+h} - \hat{L}_{T_k+h})$ | Mean Interval Width in INR Crore. Measures interval sharpness. |

### 6.2 Relative Comparison to Seasonal-Naive Baseline
Every model $m$ will report relative performance metrics against the Seasonal-Naive benchmark:
$$\text{Relative MAE}_m(h) = \frac{\text{MAE}_m(h)}{\text{MAE}_{\text{seasonal\_naive}}(h)}$$
$$\text{Skill Score}_m(h) = 1 - \frac{\text{MAE}_m(h)}{\text{MAE}_{\text{seasonal\_naive}}(h)}$$
* $\text{Skill Score} > 0$ ($\text{Relative MAE} < 1.0$): Model adds genuine predictive value beyond seasonal persistence.
* $\text{Skill Score} \le 0$: Model fails to beat naive seasonal repetition.

---

## 7. Implementation Sequence (Phase 4 Roadmap)

Upon approval, implementation will proceed through the following steps:

```
Step 1: Evaluation Metrics Engine (app/forecasting/metrics.py)
   ├── Implement MAE, RMSE, WAPE, MASE, Pinball Loss
   ├── Implement origin-specific floor epsilon_T for MAPE
   ├── Implement empirical coverage and interval width
   └── Implement Relative MAE and Skill Score calculations

Step 2: Model Estimators (app/forecasting/models.py)
   ├── Seasonal-Naive Forecaster
   ├── ETS Forecaster (statsmodels)
   ├── SARIMAX Forecaster with calendar & lagged macro regressors
   ├── Ridge Direct Multi-Step Forecaster (scikit-learn)
   └── (Optional) Constrained LightGBM Forecaster

Step 3: Prediction Interval Engine (app/forecasting/intervals.py)
   ├── Historical out-of-sample error collector
   ├── Empirical quantile interval calculator per horizon
   └── Parametric variance calibration scaling

Step 4: Rolling-Origin Backtesting Harness (app/forecasting/backtest.py)
   ├── 24-origin expanding window controller (2024-07 to 2026-06)
   ├── Strict origin-time data isolation
   ├── Independent execution for Liquid and Overnight categories
   └── Results serializer to data/processed/backtest_results.csv

Step 5: Execution Script & Reporting (scripts/run_backtest.py)
   ├── Multi-model backtest runner
   └── Generates structured markdown comparison tables by category & horizon

Step 6: Automated Test Suite (tests/test_forecasting.py)
   ├── Unit tests for metric calculations (edge cases, zero flows)
   ├── Unit tests for backtest window boundaries and leakage checks
   └── Unit tests for prediction interval calibration
```

---

## 8. Summary of Design Changes & Remaining Limitations

### 8.1 Concise List of Design Changes
1. **Model Hierarchy**: Promoted **Ridge Regression** to primary regularized ML model; relegated **LightGBM** to optional secondary exploration; reaffirmed total exclusion of deep learning.
2. **Dynamic Origin-Specific MAPE Floor**: Replaced fixed global epsilon with origin-specific $\epsilon_T = \text{Percentile}_{10}(\{|Y_t|\}_{t=1}^T)$ computed strictly on training data up to origin $T$.
3. **Out-of-Sample Prediction Intervals**: Replaced in-sample residual quantiles with **horizon-specific, historical out-of-sample forecast errors** accrued strictly prior to origin $T$.
4. **Macro Regressor Protocol**: Codified zero-leakage forward assumptions ($\Delta \text{Repo} = 0$, neutral equity return) for multi-step SARIMAX forecasting.
5. **Multi-Step Dependency**: Formally documented the non-i.i.d. nature of overlapping multi-step forecast errors across consecutive origins.
6. **Benchmark Relativity**: Mandated explicit Skill Score and Relative MAE reporting against Seasonal-Naive for all models.

### 8.2 Remaining Methodological Limitations
1. **Small Sample Constraints ($N \approx 78$)**: The post-warmup monthly sample size limits statistical power. Model complexity must remain deliberately low (linear Ridge or depth-2 trees).
2. **Statistical Resolution of 95% Coverage**: With 24 origins, each test observation represents 4.17% of coverage. 95% interval coverage cannot be verified with fine statistical precision; 80% coverage provides the more reliable calibration signal.
3. **Overlapping Horizons**: Forecast errors for $h=2$ and $h=3$ across adjacent origins are correlated ($\text{MA}(h-1)$ structure), which must be considered when evaluating performance differences.
4. **Unprecedented Macro Shocks**: If an off-cycle rate cut/hike or regulatory rule change occurs within the 3-month forecast window, models assuming constant forward policy rates will naturally experience transient forecast errors.

