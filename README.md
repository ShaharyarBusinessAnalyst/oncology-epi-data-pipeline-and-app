# 🧬 Epidemiology Data Pipeline & Patient Forecast Automation

An automated ETL pipeline that consolidates cancer epidemiology data from CDC public health sources across multiple oncology indications, applies a confidence-scoring framework, and generates patient population forecasts — served via a self-serve Streamlit app.

> **Note:** This is a sanitized, open-source version built on CDC public data. It replicates the architecture of a production pipeline delivered for a pharma industry partner under NDA.

---

## Problem

Epidemiologists manually searched 10+ public health databases to gather prevalence, incidence, and mortality data across oncology indications. Each data refresh was hours of manual work per indication, with no consistency checks across sources.

## Solution

A fully automated pipeline that:
1. Fetches live cancer mortality data from the **CDC WONDER public API** (no authentication required)
2. Scores each data point for reliability using a **tiered confidence framework** (Gold/Silver/Bronze)
3. Detects conflicts across sources and flags low-confidence records
4. Computes patient population estimates and projects them forward under **configurable growth scenarios**
5. Exports structured outputs (CSV) ready for BI tools (Tableau, Power BI)
6. Provides a **self-serve Streamlit app** so non-technical users run the pipeline without engineering support

**~85% reduction in manual data preparation time** vs prior manual process.

---

## Architecture

```
CDC WONDER API (public, no auth)
        │
        ▼
Evidence Finder → Confidence Scoring → Conflict Detection
        │
        ▼
Patient Estimate Calculator
        │
        ▼
Scenario-based Forecast (Gold/Silver/Bronze growth options)
        │
        ├── CSV Outputs (for Tableau / Power BI)
        └── Streamlit Self-Serve App
```

---

## Features

| Feature | Description |
|---|---|
| **Live CDC data** | Pulls from CDC WONDER API — no manual downloads |
| **Tiered sources** | Gold (CDC) → Silver (literature) → Bronze (web) hierarchy |
| **Confidence scoring** | Per-record reliability score based on tier, recency, completeness, conflicts |
| **Quality scorecard** | Aggregated data quality summary by indication and metric |
| **Scenario forecasting** | Configurable growth rates and horizons via YAML — no code changes |
| **Multi-indication** | 6 oncology indications out of the box; add more via config |
| **Self-serve UI** | Streamlit app with dropdowns, charts, and CSV export |
| **CSV export** | Structured outputs for Tableau, Power BI, or Excel |

---

## Supported Indications

| Indication | ICD-10 Codes |
|---|---|
| Lung & Bronchus Cancer | C33, C34 |
| Breast Cancer | C50 |
| Colorectal Cancer | C18, C19, C20 |
| Prostate Cancer | C61 |
| Non-Hodgkin Lymphoma | C82–C86 |
| Leukemia | C91–C95 |

Adding a new indication: edit `config/indications.yaml` — no code changes required.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Option 1 — Streamlit self-serve app (recommended)
streamlit run app.py

# Option 2 — CLI pipeline runner
python run_pipeline.py
```

---

## Project Structure

```
epi_pipeline/
├── app.py                          # Streamlit self-serve UI
├── run_pipeline.py                 # CLI pipeline runner
├── requirements.txt
├── config/
│   ├── indications.yaml            # Oncology indications + ICD-10 codes
│   ├── scenario_options.yaml       # Growth rate and horizon scenarios
│   └── source_tiers.yaml           # Gold/Silver/Bronze tier definitions
├── src/
│   ├── evidence_finder/
│   │   └── cdc_wonder.py           # CDC WONDER API connector
│   ├── repository/
│   │   └── confidence.py           # Confidence scoring + quality scorecard
│   └── analytics/
│       └── forecast.py             # Patient population forecasting
└── outputs/                        # Pipeline output CSVs (git-ignored)
```

---

## Configuration

**Adding a new indication** (`config/indications.yaml`):
```yaml
ovarian_cancer:
  display_name: "Ovarian Cancer"
  icd10_codes: "C56"
  metrics:
    - incidence_rate
    - mortality_rate
```

**Adding a growth scenario** (`config/scenario_options.yaml`):
```yaml
- option_id: aggressive
  label: "Aggressive growth"
  rationale: "Upper bound for market sizing"
  sources: "Assumption"
  value_numeric: 0.05
```

---

## Confidence Scoring

Each evidence record receives a score from 0–1:

| Factor | Impact |
|---|---|
| Source tier (Gold) | +0.90 base |
| Source tier (Silver) | +0.65 base |
| Source tier (Bronze) | +0.40 base |
| Recency (per year of age) | −0.02 |
| Missing definition | −0.05 |
| Missing geography | −0.03 |
| Source conflict detected | −0.10 |

---

## Tech Stack

- **Data source:** CDC WONDER public API
- **Pipeline:** Python, pandas
- **Config:** YAML
- **UI:** Streamlit
- **Exports:** CSV (Tableau / Power BI compatible)

---

## Data Source

All data is sourced from the **CDC WONDER public database** — the official U.S. federal cancer statistics system jointly operated by CDC and NCI. Data is publicly available with no authentication required.

- [CDC WONDER API documentation](https://wonder.cdc.gov/wonder/help/WONDER-API.html)
- [U.S. Cancer Statistics](https://www.cdc.gov/united-states-cancer-statistics/)
