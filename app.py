"""
Self-serve Streamlit app for the Epidemiology Data Pipeline.
Non-technical users can select indications, scenarios, and run the pipeline
without any engineering support.
"""

import streamlit as st
import pandas as pd
import yaml
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from src.evidence_finder.cdc_wonder import fetch_all_indications
from src.repository.confidence import add_confidence_scores, build_quality_scorecard
from src.analytics.forecast import (
    load_scenario_options,
    get_scenario_rate,
    compute_base_patient_estimate,
    forecast_patient_population,
    build_forecast_summary,
)

CONFIG_DIR = Path("config")

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Epidemiology Pipeline",
    page_icon="🧬",
    layout="wide"
)

st.title("🧬 Epidemiology Data Pipeline")
st.caption("Automated patient population forecasting from CDC public health data.")

# ── Load configs ─────────────────────────────────────────────────────────────
@st.cache_data
def load_configs():
    with open(CONFIG_DIR / "indications.yaml") as f:
        ind_cfg = yaml.safe_load(f)
    scenario_opts = load_scenario_options(CONFIG_DIR / "scenario_options.yaml")
    return ind_cfg, scenario_opts

ind_cfg, scenario_opts = load_configs()
all_indications = list(ind_cfg.get("indications", {}).keys())
ind_labels = {k: v["display_name"] for k, v in ind_cfg["indications"].items()}

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Pipeline Settings")

    selected = st.multiselect(
        "Select Oncology Indications",
        options=all_indications,
        default=all_indications[:3],
        format_func=lambda x: ind_labels.get(x, x)
    )

    st.divider()
    st.subheader("Forecast Scenario")

    growth_options = {
        opt["option_id"]: f"{opt['label']} ({opt['value_numeric']*100:.1f}%/yr)"
        for opt in scenario_opts["scenario_types"]["growth_rate"]
    }
    growth_scenario = st.selectbox(
        "Growth Rate Scenario",
        options=list(growth_options.keys()),
        format_func=lambda x: growth_options[x],
        index=0
    )

    horizon_options = {
        opt["option_id"]: opt["label"]
        for opt in scenario_opts["scenario_types"]["forecast_horizon"]
    }
    horizon_scenario = st.selectbox(
        "Forecast Horizon",
        options=list(horizon_options.keys()),
        format_func=lambda x: horizon_options[x],
        index=1
    )

    st.divider()
    st.subheader("Data Range")
    year_start = st.slider("Start Year", 2015, 2021, 2018)
    year_end = st.slider("End Year", year_start + 1, 2022, 2022)

    run_btn = st.button("▶ Run Pipeline", type="primary", use_container_width=True)

# ── Main content ──────────────────────────────────────────────────────────────
if not run_btn:
    st.info("Configure settings in the sidebar and click **Run Pipeline** to fetch live CDC data and generate forecasts.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Data Source", "CDC WONDER API")
    col2.metric("Indications Available", len(all_indications))
    col3.metric("Forecast Scenarios", len(growth_options))

else:
    if not selected:
        st.warning("Please select at least one indication.")
        st.stop()

    # Run pipeline
    with st.spinner("Fetching CDC WONDER data..."):
        evidence_df = fetch_all_indications(selected, year_start, year_end)

    if evidence_df.empty:
        st.error("No data retrieved from CDC WONDER. Check your connection.")
        st.stop()

    evidence_df["metric"] = "mortality_rate"
    evidence_df["geography"] = "United States"

    with st.spinner("Scoring confidence and computing forecasts..."):
        scored_df = add_confidence_scores(evidence_df)
        scorecard_df = build_quality_scorecard(scored_df)
        patient_df = compute_base_patient_estimate(scored_df)

        growth_rate = get_scenario_rate(scenario_opts, "growth_rate", growth_scenario) or 0.02
        horizon = int(get_scenario_rate(scenario_opts, "forecast_horizon", horizon_scenario) or 5)

        forecast_df = forecast_patient_population(patient_df, growth_rate=growth_rate, horizon_years=horizon)
        summary_df = build_forecast_summary(forecast_df)

    st.success(f"✓ Pipeline complete — {len(evidence_df)} evidence records processed")

    # ── Summary KPIs ────────────────────────────────────────────────────────
    st.header("📊 Forecast Summary")
    if not summary_df.empty:
        cols = st.columns(min(len(summary_df), 3))
        for i, row in summary_df.iterrows():
            with cols[i % 3]:
                st.metric(
                    label=ind_labels.get(row["indication"], row["indication"]),
                    value=f"{row['forecast_patient_estimate']:,}",
                    delta=f"{row['cagr_pct']:+.1f}% CAGR",
                    help=f"Base ({row['base_year']}): {row['base_patient_estimate']:,}"
                )

    st.divider()

    # ── Forecast chart ───────────────────────────────────────────────────────
    st.subheader("📈 Patient Population Trend & Forecast")
    if not forecast_df.empty and "patient_estimate" in forecast_df.columns:
        chart_data = forecast_df[["year", "indication", "patient_estimate", "is_forecast"]].copy()
        chart_data["indication"] = chart_data["indication"].map(ind_labels).fillna(chart_data["indication"])

        # Pivot for chart
        pivot = chart_data.pivot_table(
            index="year", columns="indication", values="patient_estimate", aggfunc="sum"
        )
        st.line_chart(pivot)

    st.divider()

    # ── Tabs for detailed data ───────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📋 Evidence Data", "🏅 Quality Scorecard", "📥 Export"])

    with tab1:
        st.subheader("Evidence Records (CDC WONDER)")
        display_cols = [c for c in ["indication", "year", "deaths", "population",
                                     "crude_rate", "age_adjusted_rate", "confidence_score",
                                     "confidence_label", "source_tier"] if c in scored_df.columns]
        st.dataframe(scored_df[display_cols], use_container_width=True)

    with tab2:
        st.subheader("Data Quality Scorecard")
        st.dataframe(scorecard_df, use_container_width=True)
        if not scorecard_df.empty and "avg_confidence" in scorecard_df.columns:
            avg = scorecard_df["avg_confidence"].mean()
            st.metric("Overall Pipeline Confidence", f"{avg:.2f} / 1.00")

    with tab3:
        st.subheader("Download Results")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                "📥 Evidence (CSV)",
                data=scored_df.to_csv(index=False),
                file_name="evidence_scored.csv",
                mime="text/csv"
            )
        with col2:
            st.download_button(
                "📥 Forecast (CSV)",
                data=forecast_df.to_csv(index=False),
                file_name="forecast_patient_population.csv",
                mime="text/csv"
            )
        with col3:
            st.download_button(
                "📥 Summary (CSV)",
                data=summary_df.to_csv(index=False),
                file_name="forecast_summary.csv",
                mime="text/csv"
            )
