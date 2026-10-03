"""Clear per-identity analysis and Provider display state when an identity ends."""

ANALYSIS_STATE_KEYS = (
    "job_analysis",
    "analysis_report",
    "legacy_analysis_report",
    "skill_editor",
    "history_report_selector",
    "demo_result",
)


def clear_identity_state(state) -> None:
    for key in tuple(state.keys()):
        if (
            key in ANALYSIS_STATE_KEYS
            or key.startswith(
                ("c2c_analysis_", "c2c_project_", "c2c_internship_", "provider_")
            )
            or key == "c2c_minimum_degree"
            or key == "model_catalog_service"
        ):
            state.pop(key, None)
    state["analysis_form_epoch"] = state.get("analysis_form_epoch", 0) + 1
    # Suppress the prior page body for one run, so old widget output cannot
    # remain visible while Streamlit processes the browser storage update.
    state["identity_just_cleared"] = True
