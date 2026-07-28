"""
src/whatif/kpi.py
====================
Replaces the old hardcoded src/whatif/constants.py::KPI_TAGS (a fixed
14-tag list ported verbatim from the original single-plant Streamlit
dashboard) with a derivation off the live config, matching
Scripts/Whatif_streamlit_dashboard_updated.py's KPI-tile logic: the union of
every predicted parameter, every constrained parameter, and any extra tags
the plant plug-in declares — so a plant/config change is reflected in the
KPI tiles without a code change.

There is no clean upstream equivalent for the old VALIDATION_TAGS constant
in the generalized reference scripts (Historical Validation Filters in the
Streamlit dashboard let the user pick *any* parameter, with no default
shortlist) — the same derived tag set is reused here as a sensible default
shortlist for that feature too, rather than inventing a new hardcoded list.
"""
from __future__ import annotations

from types import ModuleType

from src.whatif.config_io import WhatIfConfig


def derive_kpi_tags(config: WhatIfConfig, plugin: ModuleType | None) -> list[str]:
    """Order-preserving union of: Model details predicted parameters,
    Constraints parameters, and the plugin's KPI_PARAMETERS — with
    KPI_REPLACEMENTS substitution applied last."""
    tags: list[str] = []
    seen: set[str] = set()

    def _add(tag: object) -> None:
        text = str(tag).strip()
        if text and text.lower() != "nan" and text not in seen:
            seen.add(text)
            tags.append(text)

    if config.model_details_df is not None and "Predicted parameter" in config.model_details_df.columns:
        for v in config.model_details_df["Predicted parameter"]:
            _add(v)

    if config.constraints_df is not None and "Parameter" in config.constraints_df.columns:
        for v in config.constraints_df["Parameter"]:
            _add(v)

    if plugin is not None:
        for v in getattr(plugin, "KPI_PARAMETERS", []) or []:
            _add(v)

    replacements = getattr(plugin, "KPI_REPLACEMENTS", {}) or {} if plugin is not None else {}
    if replacements:
        tags = [replacements.get(t, t) for t in tags]
        deduped: list[str] = []
        seen2: set[str] = set()
        for t in tags:
            if t not in seen2:
                seen2.add(t)
                deduped.append(t)
        tags = deduped

    return tags
