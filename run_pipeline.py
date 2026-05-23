"""
Main pipeline runner.
Orchestrates: CDC WONDER fetch → confidence scoring → forecasting → export.
"""

from pathlib import Path
import pandas as pd
import yaml

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
OUTPUT_DIR = Path("outputs")


def load_indications_config() -> dict:
    with open(CONFIG_DIR / "indications.yaml") as f:
        return yaml.safe_load(f)


def run_pipeline(
    selected_indications: list = None,
    growth_scenario: str = "cdc_trend",
    forecast_horizon: str = "five_year",
    year_start: int = 2018,
    year_end: int = 2022,
    export: bool = True,
) -> dict:
    """
    Run the full epidemiology data pipeline.

    Args:
        selected_indications: List of indication keys (e.g. ['lung_cancer', 'breast_cancer']).
                              If None, runs all configured indications.
        growth_scenario: Scenario option_id from scenario_options.yaml
        forecast_horizon: Forecast horizon option_id from scenario_options.yaml
        year_start / year_end: CDC WONDER query range
        export: Whether to write outputs to CSV

    Returns:
        Dict with keys: evidence, scored, forecast, scorecard, summary
    """
    print("=" * 60)
    print("  Epidemiology Data Pipeline")
    print("=" * 60)

    # Load configs
    ind_config = load_indications_config()
    scenario_opts = load_scenario_options(CONFIG_DIR / "scenario_options.yaml")

    # Determine which indications to run
    all_indications = list(ind_config.get("indications", {}).keys())
    indications = selected_indications or all_indications
    print(f"\n[1/5] Indications: {indications}")

    # Step 1: Fetch evidence from CDC WONDER
    print(f"\n[2/5] Fetching CDC WONDER data ({year_start}-{year_end})...")
    evidence_df = fetch_all_indications(indications, year_start, year_end)

    if evidence_df.empty:
        print("  ✗ No evidence retrieved. Check CDC WONDER connectivity.")
        return {}

    print(f"  ✓ {len(evidence_df)} evidence records retrieved")

    # Standardize metric column
    evidence_df["metric"] = "mortality_rate"
    evidence_df["geography"] = "United States"

    # Step 2: Confidence scoring
    print("\n[3/5] Scoring evidence confidence...")
    scored_df = add_confidence_scores(evidence_df)
    scorecard_df = build_quality_scorecard(scored_df)
    print(f"  ✓ Confidence scored — avg: {scored_df['confidence_score'].mean():.2f}")

    # Step 3: Compute patient estimates
    print("\n[4/5] Computing patient population estimates...")
    patient_df = compute_base_patient_estimate(scored_df)

    # Get scenario parameters
    growth_rate = get_scenario_rate(scenario_opts, "growth_rate", growth_scenario) or 0.02
    horizon = int(get_scenario_rate(scenario_opts, "forecast_horizon", forecast_horizon) or 5)
    print(f"  Scenario: {growth_scenario} | Growth rate: {growth_rate*100:.1f}% | Horizon: {horizon} years")

    # Step 4: Forecast
    forecast_df = forecast_patient_population(patient_df, growth_rate=growth_rate, horizon_years=horizon)
    summary_df = build_forecast_summary(forecast_df)
    print(f"  ✓ Forecast complete — {len(summary_df)} indications")

    # Step 5: Export
    if export:
        print("\n[5/5] Exporting outputs...")
        OUTPUT_DIR.mkdir(exist_ok=True)

        scored_df.to_csv(OUTPUT_DIR / "evidence_scored.csv", index=False)
        scorecard_df.to_csv(OUTPUT_DIR / "quality_scorecard.csv", index=False)
        forecast_df.to_csv(OUTPUT_DIR / "forecast_patient_population.csv", index=False)
        summary_df.to_csv(OUTPUT_DIR / "forecast_summary.csv", index=False)

        print(f"  ✓ Outputs written to {OUTPUT_DIR}/")

    print("\n" + "=" * 60)
    print("  Pipeline complete.")
    print("=" * 60)

    return {
        "evidence": evidence_df,
        "scored": scored_df,
        "scorecard": scorecard_df,
        "forecast": forecast_df,
        "summary": summary_df,
    }


if __name__ == "__main__":
    results = run_pipeline()

    if results:
        print("\n--- Forecast Summary ---")
        print(results["summary"].to_string(index=False))

        print("\n--- Quality Scorecard ---")
        print(results["scorecard"].to_string(index=False))
