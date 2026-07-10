"""
src/whatif/config_io.py
========================
Loads the 5 relevant sheets from Config_file.xlsx into one WhatIfConfig
object, passed explicitly into the engine (src/whatif/engine.py) instead
of being re-read from disk on every call, as the original
Scripts/whatif_runner.py did.

Sheet -> field mapping (matches Scripts/Whatif_streamlit_dashboard.py's
SHEET_TO_STATE, tolerant of the two extra unused sheets that exist on the
real Config_file.xlsx: "process_param_stats" and "Model details_copy",
which are simply ignored).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

# The real Constraints sheet on disk uses this misspelled column name, and
# it's what Scripts/whatif_runner.py actually reads. Preserved deliberately —
# do not "fix" without also migrating Data/Config_file.xlsx.
CONSTRAINTS_MAX_COL = "Max vlaue"

USER_INPUTS_COLUMNS = ["Parameter", "Value", "Lower Limit", "Upper Limit", "Remark"]
CONSTRAINTS_COLUMNS = ["Parameter", "user input value", CONSTRAINTS_MAX_COL, "UOM", "Remark"]
DISPLAY_ORDER_COLUMNS = ["Sr.no", "Preferred columns"]
MODEL_DETAILS_COLUMNS = ["Predicted parameter"] + [f"Input parameter_{i}" for i in range(1, 9)]
PI_COLUMNS = ["Pi_tags", "Generalized Description", "Section"]

_SHEET_TO_FIELD = {
    "user inputs": "user_inputs_df",
    "model details": "model_details_df",
    "constraints": "constraints_df",
    "display_column_order": "display_order_df",
    "pi_generalised_name": "pi_names_df",
}


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


_SHEET_LOOKUP_NORM = {_norm_name(k): v for k, v in _SHEET_TO_FIELD.items()}


def match_sheet_to_field(sheet_name: str) -> str | None:
    """Maps a workbook sheet name to a WhatIfConfig field name, tolerant of
    spacing/casing variants (ported from Whatif_streamlit_dashboard.py's
    _match_sheet_to_state)."""
    n = _norm_name(sheet_name)
    if n in _SHEET_LOOKUP_NORM:
        return _SHEET_LOOKUP_NORM[n]
    if "pi" in n and ("general" in n or "generalis" in n or "generaliz" in n):
        return "pi_names_df"
    return None


class ConfigSchemaError(ValueError):
    """Raised when a loaded sheet doesn't have the columns the engine needs."""


def _require_columns(df: pd.DataFrame, required: list[str], sheet_label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ConfigSchemaError(
            f"Sheet '{sheet_label}' is missing expected column(s) {missing}. "
            f"Found columns: {list(df.columns)}"
        )


@dataclass
class WhatIfConfig:
    user_inputs_df: pd.DataFrame
    constraints_df: pd.DataFrame
    display_order_df: pd.DataFrame
    model_details_df: pd.DataFrame
    pi_names_df: pd.DataFrame


def _read_sheet(xl: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(xl, sheet_name=sheet_name).dropna(how="all").reset_index(drop=True)


def load_all_config(path: str) -> WhatIfConfig:
    """Reads every recognised sheet from Config_file.xlsx once. Unknown/unused
    sheets (process_param_stats, Model details_copy) are silently ignored.

    Uses `with` to explicitly close the underlying OS file handle as soon as
    reading is done. pd.ExcelFile(path) opened from a string path does NOT
    reliably release its Windows file handle just because the object goes out
    of scope — it depends on the cyclic GC running, not plain refcounting,
    since the ExcelFile/openpyxl workbook hold circular references to each
    other. Without an explicit close, every call to this function (which is
    every What-If Studio config/wizard endpoint) leaks a handle on
    Config_file.xlsx; since these endpoints are hit constantly (React Query
    refetch-on-focus, wizard actions, etc.), the file stays locked almost
    continuously, causing uploads/replacements of this same file to fail with
    a persistent (not transient) WinError 5 Access Denied."""
    found: dict[str, pd.DataFrame] = {}
    with pd.ExcelFile(path) as xl:
        for sheet in xl.sheet_names:
            field = match_sheet_to_field(sheet)
            if field is None or field in found:
                continue
            found[field] = _read_sheet(xl, sheet)

    user_inputs_df = found.get("user_inputs_df", pd.DataFrame(columns=USER_INPUTS_COLUMNS))
    constraints_df = found.get("constraints_df", pd.DataFrame(columns=CONSTRAINTS_COLUMNS))
    display_order_df = found.get("display_order_df", pd.DataFrame(columns=DISPLAY_ORDER_COLUMNS))
    model_details_df = found.get("model_details_df", pd.DataFrame(columns=MODEL_DETAILS_COLUMNS))
    pi_names_df = found.get("pi_names_df", pd.DataFrame(columns=PI_COLUMNS))

    if not constraints_df.empty:
        _require_columns(constraints_df, ["Parameter", "user input value", CONSTRAINTS_MAX_COL], "Constraints")
    if not model_details_df.empty:
        _require_columns(model_details_df, ["Predicted parameter"], "Model details")

    return WhatIfConfig(
        user_inputs_df=user_inputs_df,
        constraints_df=constraints_df,
        display_order_df=display_order_df,
        model_details_df=model_details_df,
        pi_names_df=pi_names_df,
    )
