# FINHYPE — Hackathon Demonstration Guide

**Project:** FINHYPE (Zeckathon 2026 · Problem Statement 3)  
**Target Audience:** Hackathon Judges, Quantitative Evaluators, and Treasury Risk Managers  
**Live Demo Duration:** ~5 Minutes  

---

## 1. Quick Setup & One-Command Launch

### System Requirements
* **Operating System:** Windows 10/11 (Primary), Linux, or macOS
* **Python Version:** Python 3.10 to 3.14
* **Pre-installed Environment:** Virtual environment `.venv` pre-configured in project root

### Launch Options

#### Option A: Windows PowerShell (Recommended)
```powershell
# Open terminal in project root C:\Users\Alok\Desktop\FINHYPE
.\run.ps1 -OnlyDashboard
```
*To run the complete data & forecasting pipeline before launching the dashboard:*
```powershell
.\run.ps1 -Dashboard
```

#### Option B: Windows Command Prompt (cmd.exe)
```cmd
.\run.bat --only-dashboard
```

#### Option C: Standard Python CLI
```bash
# Activate virtual environment
.\.venv\Scripts\activate

# Launch Streamlit dashboard directly
streamlit run app/dashboard.py
```

#### Option D: Linux / macOS
```bash
./run.sh --only-dashboard
```

---

## 2. Expected Startup Behavior

1. **Terminal Output**:
   ```text
   Starting Streamlit web server on http://localhost:8501 ...
     You can now view your Streamlit app in your browser.
     Local URL: http://localhost:8501
   ```
2. **Browser Display**: Automatically opens your default web browser at `http://localhost:8501`.
3. **Data Caching**: On initial startup, the app loads precomputed artifacts in `< 1.0s` from `data/processed/`.
4. **Graceful Fault Tolerance**: If precomputed files are absent, the dashboard renders an informative error banner with exact pipeline generation commands instead of an unhandled crash.

---

## 3. Recommended 5-Minute Demonstration Script

| Timeline | Dashboard Tab | Key Actions & Speaking Points | Highlighted Metric / Visual |
|:---|:---|:---|:---|
| **0:00 – 1:00** | **🏛️ Tab 1: Executive Summary** | **Introduce Problem Statement 3**: Mutual fund treasuries face predictable liquidity drains (quarterly advance-tax payments in Mar/Jun/Sep/Dec) followed by liquidity surges (Oct/Jan/Apr/Jul).<br>Show **Liquid Fund** AUM (~₹625,847 Cr) vs **Overnight Fund** AUM (~₹84,033 Cr). Highlight portfolio velocity: Overnight funds turn over **5.44x of total AUM every month** (>₹420,000 Cr in gross monthly volume). | Metric cards: AUM, Net Flow, Gross Mobilised vs Redemptions. |
| **1:00 – 2:00** | **📊 Tab 2: Historical Dynamics & AUM** | Walk through the 90-month historical trajectory (Apr 2019 – Sep 2026).<br>Point out the **Calendar Month Seasonality Profile** bar chart: Advance tax months are highlighted in red (average outflows), while post-quarter months are blue (average inflows).<br>Highlight the extreme November 2025 outflow (-₹37,624 Cr) in Overnight funds. | Two-panel historical flow/AUM chart & calendar seasonality bar chart. |
| **2:00 – 3:00** | **🎯 Tab 3: 3-Month Forward Forecasts** | Show out-of-sample forward projections for **October, November, and December 2026** (Origin: September 2026).<br>Demonstrate the **Active Cash-Buffer Policy Trajectory** selector: observe how it directly matches the model sequence deployed in Tab 4.<br>Switch to standalone **SARIMAX** or **Seasonal-Naive** to explore individual model trajectories with contextual explanation banners.<br>Inspect the redesigned, unclipped breakdown table with dedicated sub-tabs: *All Bands*, *Moderate (80%)*, and *Conservative (95%)*. | Forward trajectory chart with dual fan bands & responsive 3-view breakdown table. |
| **3:00 – 4:00** | **🛡️ Tab 4: Cash Buffer Recommendation Engine** | **The Core Deliverable**: Demonstrate dynamic liquidity sizing.<br>Formula: $\text{Buffer} = \max(\text{Base Operational Floor}, \text{Peak Cumulative Downside Deficit})$.<br>1. **Liquid Funds (3M, Moderate)**: Recommend **₹75,073 Cr (12.00% of AUM)** to absorb the severe December tax outflow.<br>2. Switch sidebar category to **Overnight Fund**: Show the 1-month buffer (**₹10,366 Cr / 12.34% of AUM** via SARIMAX).<br>3. Expand the **Multi-Month Policy Comparison**: Explain why the 3-month buffer is ₹74,130 Cr (Single-Model Baseline) vs ₹90,640 Cr (Step-Wise Stitched) due to comonotonic compounding of the historical November 2025 outlier. | Four KPI cards, monthly deficit progression bar chart, and policy comparison expander. |
| **4:00 – 4:45** | **⚖️ Tab 5: Model Benchmark & Backtest** | Show the 24-origin expanding rolling backtest (July 2024 – June 2026, 576 records).<br>Demonstrate empirical superiority: **SARIMAX achieves +14.55% Skill Score** at Horizon 1 over Seasonal-Naive for Liquid Funds.<br>Point out that Seasonal-Naive dominates for Overnight Funds at multi-month horizons due to strong year-over-year persistence. | Grouped MAE comparison bar chart & audited metrics summary table. |
| **4:45 – 5:00** | **ℹ️ Tab 6: Data Freshness & Methodology** | Conclude with model governance: zero future data leakage, strictly out-of-sample calibration, transparent comonotonicity disclosures, and 154 passing unit/integration tests. | Data sources, macro assumptions, and governance disclosures. |

---

## 4. Key Treasury Figures Quick Reference

Use these audited ground-truth figures to answer judge questions immediately:

### Liquid Fund (AUM: ₹625,847.01 Cr, Base Floor: 5.0% = ₹31,292.35 Cr)
* **1-Month (Oct 2026)**: Point Forecast $+₹75,820.52\text{ Cr}$, Downside Deficit $₹0.00\text{ Cr}$ $\implies$ **Buffer: ₹31,292.35 Cr (5.00% AUM)** [Floor-driven]
* **2-Month (Oct–Nov 2026)**: Cumulative Deficit $₹0.00\text{ Cr}$ $\implies$ **Buffer: ₹31,292.35 Cr (5.00% AUM)** [Floor-driven]
* **3-Month (Oct–Dec 2026, Moderate 80%)**: Downside Deficit $₹75,072.74\text{ Cr}$ $\implies$ **Buffer: ₹75,072.74 Cr (12.00% AUM)**
* **3-Month (Oct–Dec 2026, Conservative 95%)**: Downside Deficit $₹106,161.75\text{ Cr}$ $\implies$ **Buffer: ₹106,161.75 Cr (16.96% AUM)**

### Overnight Fund (AUM: ₹84,032.57 Cr, Base Floor: 2.5% = ₹2,100.81 Cr)
* **1-Month Standalone (Oct 2026, `SARIMAX` Preferred Model at 1M)**:
  * Moderate (80%): **₹10,366.04 Cr (12.34% AUM)**
  * Conservative (95%): **₹17,606.86 Cr (20.95% AUM)**
* **3-Month Single-Model Baseline (`Seasonal-Naive` Persistence)**:
  * Moderate (80%): **₹74,130.35 Cr (88.22% AUM)**
  * Conservative (95%): **₹118,049.89 Cr (140.48% AUM)**
* **3-Month Step-Wise Stitched Alternative (`SARIMAX` + `Seasonal-Naive` + `Seasonal-Naive`)**:
  * Moderate (80%): **₹90,640.30 Cr (107.86% AUM)**
  * Conservative (95%): **₹129,620.28 Cr (154.25% AUM)**

---

## 5. Verification Commands for Judges & Technical Auditors

If judges ask to verify the code and test coverage live:

```powershell
# Run the complete test suite (154 tests in ~12 seconds)
pytest -v --tb=short

# Run the financial calculation and model-quantile integrity tests specifically
pytest tests/test_financial_calculation_audit.py -v

# Run the end-to-end future mutation leakage test
pytest tests/test_audit_phase2.py -k "leakage" -v
```

---

## 6. Troubleshooting Common Launch Issues

| Issue | Root Cause | Immediate Fix |
|:---|:---|:---|
| `'run.bat' is not recognized as an internal or external command...` | Windows PowerShell requires explicit `./` prefix for local scripts. | Type `.\run.bat --only-dashboard` or `.\run.ps1 -OnlyDashboard`. |
| `ModuleNotFoundError: No module named 'app'` | Script executed from outside root directory or Python environment path not set. | The dashboard auto-injects project root into `sys.path`. Launch using `.\run.ps1` or `streamlit run app/dashboard.py` from project root. |
| `Missing processed datasets error on dashboard` | Processed data files have not yet been generated. | Run the pipeline once: `python run_pipeline.py --skip-backtest` (takes ~19 seconds). |
| Port 8501 already in use | Another Streamlit instance is running in the background. | Pass a custom port: `streamlit run app/dashboard.py --server.port 8502`. |
| Chart rendering blank in browser | WebGL hardware acceleration disabled or browser extension blocking scripts. | Open in Chrome/Edge incognito window, or use the pre-generated interactive standalone HTML charts in `reports/figures/`. |

---

## 7. Fallback Demonstration Plan (Zero Fabrication Guarantee)

If unforeseen hardware, network, or browser issues prevent the Streamlit dashboard from launching during judging, use this structured fallback protocol to prove every quantitative claim using production artifacts with **zero fabrication**:

### Fallback Step 1: Open Standalone Interactive Plotly Figures
FINHYPE pre-generates 6 standalone interactive HTML charts in `reports/figures/`. These require no Python web server and can be double-clicked directly from Windows File Explorer or opened via browser:
* `reports/figures/flow_trajectory_interactive.html`: Complete 90-month AUM & net flow historical trajectory.
* `reports/figures/seasonality_monthly.html`: Calendar-month seasonality bar chart showing advance-tax drain cycles.
* `reports/figures/quarter_end_flows.html`: Advance-tax quarter-end vs. non-quarter-end comparison distributions.
* `reports/figures/repo_rate_vs_flows.html`: RBI policy rate changes mapped against fund flow trends.
* `reports/figures/outliers_distribution.html`: Box plots showing extreme flow outliers including November 2025.
* `reports/figures/churn_velocity.html`: Gross turnover and portfolio velocity ratios.

### Fallback Step 2: Live Command-Line Verification
Run the audited regression check directly in the terminal to print all forward recommendations and model metrics to console:
```powershell
python -c "
import pandas as pd
from app.services.forward_forecasting import get_forward_recommendation, FORWARD_RESULTS_PATH
df = pd.read_csv(FORWARD_RESULTS_PATH)
for cat in ['Liquid Fund', 'Overnight Fund']:
    print(f'=== {cat} ===')
    for h in [1, 3]:
        r = get_forward_recommendation(cat, h, 'moderate', forward_df=df)
        print(f'H={h}M Buffer: ₹{r.recommended_buffer_cr:,.2f} Cr ({r.recommended_buffer_pct_aum:.2f}% AUM) [Model: {r.preferred_model}]')
"
```
Output confirms:
* Liquid Fund 1M: ₹31,292.35 Cr (5.00% AUM) [SARIMAX]
* Liquid Fund 3M: ₹75,072.74 Cr (12.00% AUM) [SARIMAX]
* Overnight Fund 1M: ₹10,366.04 Cr (12.34% AUM) [SARIMAX]
* Overnight Fund 3M: ₹74,130.35 Cr (88.22% AUM) [Seasonal-Naive]

### Fallback Step 3: Inspect Production CSV Artifacts
Open the audited CSV tables directly in Excel or terminal:
* `data/processed/forward_forecasts_3m.csv`: Point forecasts, 80% & 95% error quantiles for all 24 configurations.
* `data/processed/backtest_metrics_summary.csv`: Audited MAE, RMSE, WAPE, MASE, Skill Scores, and coverage.


