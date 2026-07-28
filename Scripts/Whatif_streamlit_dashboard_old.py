
# -*- coding: utf-8 -*-
"""
YP-OLF1 Enterprise What-If Platform
====================================================================
PART-1 : Imports | Page Config | CSS | Historian loading |
         PI_generalised_Name loading | Session states |
         Tag segregation functions
PART-2 : Configuration Hub | Plant Configuration Wizard |
         CGC / PRC / ERC stage selection | Furnace selection |
         Automatic PI mapping generation | Mapping export
PART-3 : What-if Dashboard | Generated tag selection |
         Timestamp selection | Baseline values |
         User override inputs | whatif_analysis execution
PART-4 : KPI cards | Actual vs Estimated table |
         Change highlighting | Historical validation | CSV export
====================================================================
"""

# =====================================================================
# PART-1  |  IMPORTS
# =====================================================================
import io
import os
import re
import traceback
import subprocess
import sys
from glob import glob

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------
# Model-training file layout (matches Model_development_and_
# static_whatif_testing.py, which reads "..\Data" and writes
# "..\Results\Model" relative to its own folder):
#
#   <parent>/
#     ├── Data/DMC_Screen_tags_data.xlsx   (sheets: PI data, Furnace data)
#     ├── Data/Config_file.xlsx            (PI mapping + Model details)
#     ├── Results/Model/*.pkl              (trained model artefacts)
#     └── <app folder>/Whatif_streamlit_dashboard.py
#                       Model_development_and_static_whatif_testing.py
# ---------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_DATA_DIR = os.path.normpath(os.path.join(APP_DIR, "..", "Data"))
RESULTS_DIR = os.path.normpath(os.path.join(APP_DIR, "..", "Results"))
MODEL_DIR = os.path.join(RESULTS_DIR, "Model")
MODEL_SCRIPT = os.path.join(APP_DIR, "Model_development_and_static_whatif_testing.py")
TRAIN_WORKBOOK = os.path.join(TRAIN_DATA_DIR, "DMC_Screen_tags_data.xlsx")
# If this file exists, models were already trained -> training is OPTIONAL
RAW_SIM_FILE = os.path.join(RESULTS_DIR, "Raw_data_plus_simulated_data.xlsx")

try:
    from pandas.io.formats.style import Styler as _PdStyler
except Exception:  # noqa: BLE001
    _PdStyler = None

# ---------------------------------------------------------------
# Safe import of the what-if engine. The UI must never hard-crash
# with a raw traceback if the backend module is missing/broken.
# ---------------------------------------------------------------
WHATIF_IMPORT_ERROR = None
try:
    from whatif_runner import load_process_data, whatif_analysis
except Exception as _imp_err:  # noqa: BLE001
    WHATIF_IMPORT_ERROR = _imp_err
    load_process_data = None
    whatif_analysis = None

# =====================================================================
# PART-1  |  PAGE CONFIG
# =====================================================================
st.set_page_config(
    page_title="YP-OLF1 What-If Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =====================================================================
# PART-1  |  CSS  (dark control-room theme)
# =====================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

.stApp {
    background: radial-gradient(circle at top right, #1e293b, #0f172a);
    color: #f8fafc;
    font-family: 'Inter', -apple-system, sans-serif;
}

/* ---------- Headings ---------- */
h1 {
    background: linear-gradient(90deg, #38bdf8, #818cf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 34px !important;
    font-weight: 800 !important;
    margin-bottom: 4px;
}
h2, h3, h4 {
    color: #f1f5f9 !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}
label {
    color: #e2e8f0 !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background-color: #0b1220 !important;
    border-right: 1px solid rgba(255,255,255,0.08) !important;
}
section[data-testid="stSidebar"] * { color: #f1f5f9 !important; }
section[data-testid="stSidebar"] h3 {
    color: #38bdf8 !important;
    font-size: 13px !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 14px;
}

/* ---------- Tabs ---------- */
button[data-baseweb="tab"] {
    font-size: 15px !important;
    font-weight: 600 !important;
    color: #94a3b8 !important;
    transition: all .2s ease;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #38bdf8 !important;
    border-bottom-color: #38bdf8 !important;
}

/* ---------- Inputs ---------- */
div[data-baseweb="select"] > div,
.stTextInput input, .stNumberInput input {
    background-color: #1e293b !important;
    color: #f8fafc !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #38bdf8 !important;
    box-shadow: 0 0 0 1px #38bdf8 !important;
}
div[data-baseweb="select"] span { color: #f8fafc !important; font-weight: 500 !important; }

/* ---------- Tables ---------- */
[data-testid="stDataFrame"], .stDataEditor {
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    background-color: #1e293b !important;
}

/* ---------- Buttons ---------- */
.stButton > button, .stDownloadButton > button {
    background: linear-gradient(135deg, #3b82f6, #1d4ed8) !important;
    color: #fff !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 10px 24px !important;
    width: 100%;
    box-shadow: 0 4px 12px rgba(59,130,246,0.25);
    transition: all .2s ease-in-out;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(59,130,246,0.35);
}
.stDownloadButton > button {
    background: linear-gradient(135deg, #10b981, #059669) !important;
    box-shadow: 0 4px 12px rgba(16,185,129,0.20);
}

/* ---------- Cards ---------- */
.executive-card {
    background-color: rgba(30,41,59,0.4);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
}
.wizard-chip {
    display: inline-block;
    padding: 4px 12px;
    margin: 2px 6px 2px 0;
    border-radius: 999px;
    background: rgba(56,189,248,0.12);
    border: 1px solid rgba(56,189,248,0.35);
    color: #7dd3fc;
    font-size: 12px;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
}
.kpi-value { font-family: 'JetBrains Mono', monospace; }

/* Expander polish */
details {
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# PART-1  |  HISTORIAN LOADING (cached, defensive)
# =====================================================================
@st.cache_data(show_spinner="Loading historian process data...")
def get_cached_process_data() -> pd.DataFrame:
    """
    Loads historical data from the historian and normalises it:
      - forces a proper DatetimeIndex (invalid rows dropped)
      - sorts chronologically
      - drops fully-empty columns
    Raises RuntimeError with a readable message on any failure.
    """
    if load_process_data is None:
        raise RuntimeError(
            "Backend module 'whatif_runner' could not be imported: "
            f"{WHATIF_IMPORT_ERROR}"
        )
    raw = load_process_data()
    if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
        raise RuntimeError("Historian returned an empty dataset.")

    out = raw.copy()
    out.index = pd.to_datetime(out.index, errors="coerce")
    out = out[out.index.notna()].sort_index()
    out = out.dropna(axis=1, how="all")
    if out.empty:
        raise RuntimeError("No rows with valid timestamps found in historian data.")
    return out


# =====================================================================
# PART-1  |  PI_generalised_Name LOADING (cached, multi-source)
# =====================================================================
PI_SHEET = "PI_generalised_Name"
PI_COLUMNS = ["Pi_tags", "Generalized Description", "Section"]

# Sheet name (normalised) -> session-state key
SHEET_TO_STATE = {
    "user inputs": "user_inputs_df",
    "model details": "model_details_df",
    "constraints": "constraints_df",
    "display_column_order": "display_order_df",
    "pi_generalised_name": "pi_names_df",
    "lbt_input": "lbt_input_df",
}


def _norm_name(name: str) -> str:
    """'PI generalised Tags ' -> 'pigeneralisedtags' (robust sheet matching)."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


_SHEET_LOOKUP_NORM = {_norm_name(k): v for k, v in SHEET_TO_STATE.items()}


def _match_sheet_to_state(sheet_name: str):
    """Maps a workbook sheet to a session key, tolerant of naming variants.
    Any sheet containing both 'pi' and 'general' (e.g. 'PI generalised tags')
    is treated as the PI tag dictionary."""
    n = _norm_name(sheet_name)
    if n in _SHEET_LOOKUP_NORM:
        return _SHEET_LOOKUP_NORM[n]
    if "pi" in n and ("general" in n or "generalis" in n or "generaliz" in n):
        return "pi_names_df"
    return None


def _candidate_config_paths() -> list:
    """
    CONFIG FILE SEARCH PATH (first hit wins):
      1. <app folder>/Config_file.xlsx
      2. <app folder>/Data/Config_file.xlsx
      3. <one folder back>/Data/Config_file.xlsx   <- plant deployment layout
      4. same three locations for PI_generalised_Name.xlsx
    Filename matching is case-insensitive.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [
        here,
        os.path.join(here, "Data"),
        os.path.abspath(os.path.join(here, "..", "Data")),
        os.getcwd(),
        os.path.join(os.getcwd(), "Data"),
        os.path.abspath(os.path.join(os.getcwd(), "..", "Data")),
    ]
    seen_dirs, paths = set(), []
    for d in dirs:
        d = os.path.normpath(d)
        if d in seen_dirs or not os.path.isdir(d):
            continue
        seen_dirs.add(d)
        try:
            files = os.listdir(d)
        except OSError:
            continue
        for want in ("config_file.xlsx", "pi_generalised_name.xlsx"):
            for f in files:
                if f.lower() == want or (_norm_name(f).startswith("configfile") and f.lower().endswith(".xlsx")):
                    paths.append(os.path.join(d, f))
    # de-duplicate, preserve priority order
    out, seen = [], set()
    for p in paths:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out


@st.cache_data(show_spinner=False)
def autoload_config_from_disk() -> tuple:
    """
    AUTOMATIC CONFIG LOADING — no upload required.
    Walks the search path above (app folder, ./Data, ../Data) and loads
    every recognised sheet. Returns ({session_key: DataFrame}, source_path).
    The front-end upload remains available as an OPTIONAL override.
    """
    found: dict = {}
    source = None
    for path in _candidate_config_paths():
        try:
            xl = pd.ExcelFile(path)
        except Exception:  # noqa: BLE001
            continue
        loaded_any = False
        for sheet in xl.sheet_names:
            state_name = _match_sheet_to_state(sheet)
            if state_name is None or state_name in found:
                continue
            try:
                sheet_df = (pd.read_excel(xl, sheet_name=sheet)
                            .dropna(how="all").reset_index(drop=True))
            except Exception:  # noqa: BLE001
                continue
            found[state_name] = sheet_df
            loaded_any = True
        # Standalone PI file may only contain the dictionary sheet
        if loaded_any and source is None:
            source = path
        if len(found) >= len(SHEET_TO_STATE):
            break
    return found, source


def normalize_pi_df(pi_df: pd.DataFrame) -> pd.DataFrame:
    """Cleans the PI dictionary: trims text, title-cases Section, drops blanks.
    Blank/missing Section values are auto-inferred (clubbed) from tag names."""
    if pi_df is None or pi_df.empty:
        return pd.DataFrame(columns=PI_COLUMNS)
    out = pi_df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    for col in PI_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out = out[[c for c in out.columns if c in set(PI_COLUMNS) | set(out.columns)]]
    out["Pi_tags"] = out["Pi_tags"].astype(str).str.strip()
    out["Generalized Description"] = out["Generalized Description"].astype(str).str.strip()
    out["Section"] = (
        out["Section"].astype(str).str.strip().str.title()
        .replace({"Nan": "", "None": "",
                  "Cgc": "CGC", "Prc": "PRC", "Erc": "ERC"})
    )
    # Club unclassified tags into their section automatically
    blank = out["Section"] == ""
    if blank.any():
        out.loc[blank, "Section"] = out.loc[blank, "Generalized Description"].map(infer_section)
    out = out[(out["Pi_tags"] != "") & (out["Pi_tags"].str.lower() != "nan")]
    return out.reset_index(drop=True)


# =====================================================================
# PART-1  |  SESSION STATES (single source of truth)
# =====================================================================
_SESSION_DEFAULTS = {
    "user_inputs_df": pd.DataFrame(
        columns=["Parameter", "Value", "Lower Limit", "Upper Limit", "Remark"]),
    "model_details_df": pd.DataFrame(
        columns=["Predicted parameter"] + [f"Input parameter_{i}" for i in range(1, 9)]),
    "constraints_df": pd.DataFrame(
        columns=["Parameter", "user input value", "Max value", "UOM", "Remark"]),
    "display_order_df": pd.DataFrame(columns=["Sr.no", "Preferred columns"]),
    "pi_names_df": pd.DataFrame(columns=PI_COLUMNS),
    "lbt_input_df": pd.DataFrame(
        columns=["Iteration No", "Match_tags", "Tolerance_minimum",
                 "Tolerance_maximum", "Match_Tag_Decimal",
                 "performance_tag", "direction"]),
    # Wizard outputs
    "generated_pi_mapping": pd.DataFrame(columns=PI_COLUMNS),
    "generated_tags": [],
    "wizard_selection": {},
    "pi_source": "session memory",
    # PI Tag Mapping sheet stays hidden until a config workbook containing
    # the model mapping sheet is uploaded through the UI
    "config_uploaded_via_ui": False,
    # Simulation overrides in the What-if Dashboard stay hidden until the
    # user clicks "Proceed to What-if Dashboard" in the case setup tab
    "setup_complete": False,
    # Training workflow gates
    "training_data_ready": False,   # PI data + Furnace data sheets saved to disk
    "models_trained": False,        # model script ran OK and pkl files exist
    # Bumped on every config upload so the data editors re-render fresh data
    "editor_rev": 0,
}

for _key, _default in _SESSION_DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = (
            _default.copy() if isinstance(_default, (pd.DataFrame, dict, list)) else _default
        )



# =====================================================================
# PART-1  |  TAG SEGREGATION FUNCTIONS
# =====================================================================
_ORDINAL_TO_INT = {"1ST": 1, "2ND": 2, "3RD": 3, "4TH": 4, "5TH": 5,
                   "6TH": 6, "7TH": 7, "8TH": 8}
_STAGE_RE = re.compile(r"(1ST|2ND|3RD|[4-8]TH)[_\s]*(?:STG|STAGE)", re.IGNORECASE)
_FURNACE_RE = re.compile(r"_F(\d{1,2})(?:_|$)")
_FURNACE_RANGE_RE = re.compile(r"_F(\d{1,2})_(\d{1,2})(?:_|$)")


def extract_stage_number(tag: str):
    """Returns compressor stage number embedded in a tag name, else None.
    e.g. 'CGC_5TH_STG_DISCH_PRES' -> 5 ; 'PRC_1ST_STAGE_Suction_FLOW' -> 1
    """
    if not isinstance(tag, str):
        return None
    m = _STAGE_RE.search(tag.upper())
    return _ORDINAL_TO_INT.get(m.group(1).upper()) if m else None


def extract_furnace_numbers(tag: str):
    """Returns the set of furnace numbers referenced by a tag, else empty set.
    Handles single ('Total_ET1NE_Feed_F7' -> {7}) and range
    ('Quench_tower_feed_temp_F6_12' -> {6..12}) patterns.
    """
    if not isinstance(tag, str):
        return set()
    rng = _FURNACE_RANGE_RE.search(tag)
    if rng:
        lo, hi = int(rng.group(1)), int(rng.group(2))
        if lo <= hi <= 20:
            return set(range(lo, hi + 1))
    single = _FURNACE_RE.search(tag)
    if single:
        return {int(single.group(1))}
    return set()


def segregate_tags_by_section(pi_df: pd.DataFrame) -> dict:
    """Splits the PI dictionary into {Section: DataFrame} groups."""
    if pi_df is None or pi_df.empty or "Section" not in pi_df.columns:
        return {}
    return {sec: grp.reset_index(drop=True)
            for sec, grp in pi_df.groupby("Section", dropna=False)}


def available_stages(pi_df: pd.DataFrame, section: str) -> list:
    """Sorted list of stage numbers present in a compressor section."""
    if pi_df is None or pi_df.empty:
        return []
    sub = pi_df[pi_df["Section"].str.upper() == section.upper()]
    stages = {extract_stage_number(t) for t in sub["Generalized Description"]}
    return sorted(s for s in stages if s is not None)


def available_furnaces(pi_df: pd.DataFrame) -> list:
    """Sorted list of furnace numbers detected in the Furnace section."""
    if pi_df is None or pi_df.empty:
        return []
    sub = pi_df[pi_df["Section"].str.upper() == "FURNACE"]
    nums = set()
    for t in sub["Generalized Description"]:
        nums |= extract_furnace_numbers(t)
    return sorted(nums)


def generate_pi_mapping(pi_df: pd.DataFrame,
                        cgc_stages: list,
                        prc_stages: list,
                        erc_stages: list,
                        furnaces: list) -> pd.DataFrame:
    """
    AUTOMATIC PI MAPPING GENERATION
    Builds the active tag mapping for the configured plant line-up:
      - Compressor sections (CGC/PRC/ERC): stage-numbered tags kept only
        for selected stages; stage-agnostic tags always kept.
      - Furnace section: furnace-numbered tags kept only for selected
        furnaces (range tags kept if ANY selected furnace is in range);
        furnace-agnostic tags always kept.
      - All other sections (Quench, Cold, ...) kept in full.
    """
    if pi_df is None or pi_df.empty:
        return pd.DataFrame(columns=PI_COLUMNS)

    stage_sel = {"CGC": set(cgc_stages or []),
                 "PRC": set(prc_stages or []),
                 "ERC": set(erc_stages or [])}
    furnace_sel = set(furnaces or [])

    def _keep(row) -> bool:
        section = str(row.get("Section", "")).upper()
        tag = str(row.get("Generalized Description", ""))
        if section in stage_sel:
            stg = extract_stage_number(tag)
            return True if stg is None else stg in stage_sel[section]
        if section == "FURNACE":
            f_nums = extract_furnace_numbers(tag)
            return True if not f_nums else bool(f_nums & furnace_sel)
        return True

    mask = pi_df.apply(_keep, axis=1)
    return pi_df[mask].reset_index(drop=True)


def fmt_num(val, force_sign: bool = False) -> str:
    """Display formatting rule: 0 decimals >= 1000, else 1 decimal."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)
    sign = "+" if force_sign else ""
    return f"{v:{sign}.0f}" if abs(v) >= 1000 else f"{v:{sign}.1f}"


# ---------------------------------------------------------------
# Seed ALL config sheets from disk once (upload in Tab-1 is an
# OPTIONAL override, not a requirement).
# ---------------------------------------------------------------
if not st.session_state.get("config_autoloaded", False):
    _disk_sheets, _disk_source = autoload_config_from_disk()
    for _state_name, _sheet_df in _disk_sheets.items():
        if _sheet_df is None or _sheet_df.empty:
            continue
        if _state_name == "pi_names_df":
            _sheet_df = normalize_pi_df(_sheet_df)
        st.session_state[_state_name] = _sheet_df
    if _disk_sheets:
        st.session_state["pi_source"] = f"auto-loaded from {_disk_source}"
    st.session_state["config_autoloaded"] = True

# ---------------------------------------------------------------
# Boot the historian. If it fails, show a friendly diagnostic and
# stop cleanly instead of a raw traceback.
# ---------------------------------------------------------------
try:
    df = get_cached_process_data()
except Exception as boot_err:  # noqa: BLE001
    st.title("YP OLF1 What-if Dashboard")
    st.error(
        "🚨 **The historian dataset could not be loaded.**\n\n"
        f"Details: `{boot_err}`\n\n"
        "Checklist:\n"
        "1. `whatif_runner.py` is in the same folder as this app.\n"
        "2. `load_process_data()` returns a timestamp-indexed DataFrame.\n"
        "3. The historian source file/connection is reachable."
    )
    with st.expander("🔧 Full technical traceback"):
        st.code(traceback.format_exc())
    st.stop()

tag_options = sorted(df.columns.astype(str).tolist())

# ---------------------------------------------------------------
# Streamlit version compatibility: 'use_container_width' is
# deprecated on newer releases in favour of width='stretch'.
# ---------------------------------------------------------------
import inspect as _inspect
try:
    _HAS_WIDTH_KW = "width" in _inspect.signature(st.button).parameters
except Exception:  # noqa: BLE001
    _HAS_WIDTH_KW = False
FULL_WIDTH = {"width": "stretch"} if _HAS_WIDTH_KW else {"use_container_width": True}


# =====================================================================
# APP TITLE + TOP-LEVEL TABS
# =====================================================================
st.title("YP OLF1 What-if Dashboard")
st.caption("Ethylene plant What-if senario development · Configuration → Run What - if → Validation with historical data")

tab0, tab1, tab2 = st.tabs(["📖 Overview", "⚙️ What-if case setup", "📊 What-if Dashboard"])


# =====================================================================
# TAB 0 : OVERVIEW — README-style instructions for running the dashboard
# =====================================================================
with tab0:

    # st.markdown('<div class="executive-card">', unsafe_allow_html=True)
    st.subheader("📖 About this Dashboard")
    st.markdown(
        "The **YP-OLF1 What-If Platform** lets you simulate *what-if* scenarios "
        "on the ethylene plant using historian process data and trained models. "
        "You configure the plant line-up once, then override selected process "
        "parameters and instantly compare **Actual vs Estimated** outcomes, "
        "validated against correlated historical snapshots."
    )
    st.markdown(
        '<span class="wizard-chip">1️⃣ Configure</span> '
        '<span class="wizard-chip">2️⃣ Run What-if</span> '
        '<span class="wizard-chip">3️⃣ Validate with history</span>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    ov1, ov2 = st.columns(2)

    with ov1:
        # st.markdown('<div class="executive-card">', unsafe_allow_html=True)
        st.subheader("🚀 How to Run")
        st.markdown(
            "**Prerequisites**\n"
            "- User needs to create generalized tag names and define the corresponding sections based on the existing config file sheet name `PI_generalised_Name`\n"
            "- The cleaned data should be stored in the `DMC_Screen_tags_data` Excel file with separate sheets named `PI data` and `Furnace data`\n"
            "- User inputs should be documented in the config file in a tabular format, including the respective lower and upper operating limits\n"
            "- In the config file `Constraints sheet`, users should define the required parameters along with their input values and maximum allowable limits\n"
            "- The `display_column_order` configuration should be specified to control the sequence of columns, ensuring that important columns are displayed at the top\n"
            "- Python with `streamlit`, `pandas`, `numpy`, `openpyxl` installed\n"
            "- `whatif_runner.py` (backend engine) in the **same folder** as this app\n"
            "- Historian data reachable via `load_process_data()`\n\n"
            "**Start the app**\n"
            "```bash\n"
            "streamlit run Whatif_streamlit_dashboard.py\n"
            "```\n"
            "The dashboard opens in your browser (default: `http://localhost:8501`)."
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # st.markdown('<div class="executive-card">', unsafe_allow_html=True)
        st.subheader("📂 Config File Locations")
        st.markdown(
            "`Config_file.xlsx` / `PI_generalised_Name.xlsx` are auto-detected "
            "from (first hit wins):\n"
            "1. The **app folder**\n"
            "2. `./Data/` inside the app folder\n"
            "3. `../Data/` one level up (plant deployment layout)\n\n"
            "A front-end upload in **⚙️ What-if case setup** is always available "
            "as an optional override."
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with ov2:
        # st.markdown('<div class="executive-card">', unsafe_allow_html=True)
        st.subheader("🧭 Step-by-Step Workflow")
        st.markdown(
            "**Step 1 — What-if case setup (⚙️ tab)**\n"
            "- Check the *Configuration Source* status chips (PI Tag Mapping / Model Mapping)\n"
            "- Answer the *Plant Configuration Wizard* line-up questions "
            "(CGC / PRC / ERC stages, furnaces) and click **⚡ Generate PI Mapping**\n"
            "- In the preview, the `Pi_tags` column starts **empty** — fill in the raw "
            "PI tags, or export the mapping and fill it offline\n"
            "- Upload the completed config workbook (with the **model mapping** sheet) — "
            "the *PI Tag Mapping* editor then appears with all columns populated\n"
            "- **Step A:** upload **DMC_Screen_tags_data.xlsx** — one workbook "
            "containing both the **PI data** and **Furnace data** sheets — and save it\n"
            "- Fill in the **🧠 Model Mapping** sheet\n"
            "- **Step B:** if `Raw_data_plus_simulated_data.xlsx` already exists in "
            "the `Results` folder, training is **skipped automatically** (retraining "
            "stays optional). Otherwise click **🧠 Train models** — this runs "
            "`Model_development_and_static_whatif_testing.py` and saves the model "
            "`.pkl` files into the `Results/Model` folder\n"
            "- Use **📥 Generate config file** to export the final 2-sheet workbook\n"
            "- Click **🚀 Proceed to What-if Dashboard** (unlocked after training)\n\n"
            "**Step 2 — What-if Dashboard (📊 tab)**\n"
            "- Pick a timestamp to load baseline (actual) values\n"
            "- Override one or more input parameters within their limits\n"
            "- Run the analysis to see KPI cards and the Actual vs Estimated table\n\n"
            "**Step 3 — Validation**\n"
            "- Tune the sidebar *Validation Filters* to find matching historical "
            "snapshots and export the unified comparison CSV"
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # st.markdown('<div class="executive-card">', unsafe_allow_html=True)
        st.subheader("🛠️ Troubleshooting")
        st.markdown(
            "- **Historian could not be loaded** → check `whatif_runner.py` is present "
            "and `load_process_data()` returns a timestamp-indexed DataFrame\n"
            "- **Wizard inactive / dictionary empty** → place `PI_generalised_Name.xlsx` "
            "or `Config_file.xlsx` on the search path, or upload a workbook\n"
            "- **PI Tag Mapping editor not visible** → it appears only after uploading "
            "a config workbook containing the model mapping sheet\n"
            "- **No historical snapshots match** → widen the validation filter ranges "
            "in the sidebar"
        )
        st.markdown('</div>', unsafe_allow_html=True)


# =====================================================================
# PART-2  |  TAB 1 : CONFIGURATION HUB
# =====================================================================
with tab1:

    # -----------------------------------------------------------------
    # 2.1  Configuration source — auto-loaded from disk;
    #      front-end upload is an OPTIONAL override
    # -----------------------------------------------------------------
    # st.markdown('<div class="executive-card">', unsafe_allow_html=True)
    st.subheader("🎛️ Configuration Source")

    _pi_ok = not st.session_state["pi_names_df"].empty
    _model_ok = not st.session_state["model_details_df"].empty
    status_chips = "  ".join([
        f'<span class="wizard-chip">🏷️ PI Tag Mapping: '
        f'{len(st.session_state["pi_names_df"]) if _pi_ok else "missing"}</span>',
        f'<span class="wizard-chip">🧠 Model Mapping: '
        f'{len(st.session_state["model_details_df"]) if _model_ok else "missing"}</span>',
    ])
    if _pi_ok or _model_ok:
        st.markdown(
            f"✅ **Config auto-loaded** ({st.session_state['pi_source']}) — {status_chips}",
            unsafe_allow_html=True,
        )
    else:
        st.warning("No Config_file.xlsx found (searched the app folder, ./Data and ../Data). "
                   "Use the optional upload below, or place the file on disk and reload.")

    with st.expander("📂 Optional: upload a config workbook to override", expanded=False):
        uploaded_config = st.file_uploader(
            "Config_file.xlsx (optional — disk config is used automatically)",
            type=["xlsx"],
        )
        if uploaded_config is not None:
            try:
                excel_file = pd.ExcelFile(uploaded_config)
                loaded = []
                loaded_states = []
                for sheet in excel_file.sheet_names:
                    state_name = _match_sheet_to_state(sheet)
                    if state_name is None:
                        continue
                    sheet_df = (pd.read_excel(excel_file, sheet_name=sheet)
                                .dropna(how="all").reset_index(drop=True))
                    if state_name == "pi_names_df":
                        sheet_df = normalize_pi_df(sheet_df)
                        st.session_state["pi_source"] = "uploaded workbook"
                    st.session_state[state_name] = sheet_df
                    loaded.append(sheet)
                    loaded_states.append(state_name)
                if loaded:
                    st.success(f"✅ Loaded sheets: {', '.join(loaded)}")
                    # Reveal the PI Tag Mapping editor only when the uploaded
                    # config workbook includes the model mapping sheet
                    if "model_details_df" in loaded_states:
                        st.session_state["config_uploaded_via_ui"] = True
                        # Show the uploaded model mapping IN FULL — predicted
                        # parameters AND input parameters. Mark as initialized
                        # so the template-blanking step never touches it.
                        st.session_state["model_mapping_initialized"] = True
                        # Force the data editors to re-render the fresh data
                        # (a reused editor key can keep showing stale rows)
                        st.session_state["editor_rev"] += 1
                else:
                    st.warning("No recognised sheets found in the uploaded workbook.")
            except Exception as e:  # noqa: BLE001
                st.error(f"⚠️ Could not parse the workbook: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # 2.2  PLANT CONFIGURATION WIZARD
    #      CGC / PRC / ERC stage selection + Furnace selection
    #      -> Automatic PI mapping generation -> Mapping export
    # -----------------------------------------------------------------
    # st.markdown('<div class="executive-card">', unsafe_allow_html=True)
    st.subheader("🧙 Plant Configuration Wizard")

    pi_master = st.session_state["pi_names_df"]
    if not pi_master.empty:
        st.caption(f"PI tag dictionary: {st.session_state['pi_source']}"
                   " · no config upload required")

    if pi_master.empty:
        st.info(
            "💡 The master PI tag dictionary (**PI_generalised_Name**) is empty. "
            "Place `PI_generalised_Name.xlsx` (or `Config_file.xlsx`) next to the app, "
            "or upload a config workbook above, to activate the wizard."
        )
    else:
        section_groups = segregate_tags_by_section(pi_master)
        sec_summary = "  ".join(
            f'<span class="wizard-chip">{sec}: {len(grp)}</span>'
            for sec, grp in sorted(section_groups.items())
        )
        st.markdown(f"**Tag dictionary loaded** — {len(pi_master)} tags across sections:", unsafe_allow_html=True)
        st.markdown(sec_summary, unsafe_allow_html=True)
        # st.markdown("<br>", unsafe_allow_html=True)

        cgc_all = available_stages(pi_master, "CGC")
        prc_all = available_stages(pi_master, "PRC")
        erc_all = available_stages(pi_master, "ERC")
        furnace_all = available_furnaces(pi_master)

        st.markdown("###### 🗨️ Answer the plant line-up questions — the wizard "
                    "will automatically club the matching tags per section "
                    "(CGC / PRC / ERC / Furnace).")

        def _ask_count(label: str, detected: list, key: str) -> int:
            """Question-style numeric answer, e.g. 'How many CGC ...?' -> 5."""
            max_n = max(detected) if detected else 0
            if max_n == 0:
                st.caption(f"⚠️ No numbered tags detected for this question.")
                return 0
            return int(st.number_input(
                label, min_value=0, max_value=max_n, value=max_n, step=1, key=key,
                help=f"Detected in the tag dictionary: up to {max_n}. "
                     "Answering N keeps tags numbered 1 to N.",
            ))

        wz1, wz2 = st.columns(2)
        with wz1:
            st.markdown("##### 🌀 CGC — Cracked Gas Compressor")
            n_cgc = _ask_count("How many CGC compressor stages are there?", cgc_all, "wiz_cgc_n")
            st.markdown("##### 🧊 ERC — Ethylene Refrigeration")
            n_erc = _ask_count("How many ERC compressor stages are there?", erc_all, "wiz_erc_n")
        with wz2:
            st.markdown("##### ❄️ PRC — Propylene Refrigeration")
            n_prc = _ask_count("How many PRC compressor stages are there?", prc_all, "wiz_prc_n")
            st.markdown("##### 🔥 Furnaces")
            n_furnace = _ask_count("How many furnaces are there?", furnace_all, "wiz_furnace_n")

        # Answering "5" for CGC clubs CGC stage tags 1..5 under Section=CGC, etc.
        cgc_stages = [s for s in cgc_all if s <= n_cgc]
        prc_stages = [s for s in prc_all if s <= n_prc]
        erc_stages = [s for s in erc_all if s <= n_erc]
        furnaces = [f for f in furnace_all if f <= n_furnace]

        ans_chips = "  ".join(
            f'<span class="wizard-chip">{name}: {n}</span>'
            for name, n in [("CGC stages", n_cgc), ("PRC stages", n_prc),
                            ("ERC stages", n_erc), ("Furnaces", n_furnace)]
        )
        # st.markdown(f"**Your answers →** {ans_chips}", unsafe_allow_html=True)
        # st.markdown("<br>", unsafe_allow_html=True)

        gen_col, clr_col = st.columns([3, 1])
        with gen_col:
            run_wizard = st.button("⚡ Generate PI Mapping for this line-up", **FULL_WIDTH)
        with clr_col:
            if st.button("♻️ Reset mapping", **FULL_WIDTH):
                st.session_state["generated_pi_mapping"] = pd.DataFrame(columns=PI_COLUMNS)
                st.session_state["generated_tags"] = []
                st.session_state["wizard_selection"] = {}
                st.toast("Wizard mapping cleared.", icon="♻️")

        if run_wizard:
            mapping = generate_pi_mapping(pi_master, cgc_stages, prc_stages, erc_stages, furnaces)
            gen_tags = [t for t in mapping["Generalized Description"].dropna().unique()
                        if t in df.columns]
            st.session_state["generated_pi_mapping"] = mapping
            st.session_state["generated_tags"] = gen_tags
            st.session_state["wizard_selection"] = {
                "CGC stages (answered)": [n_cgc], "PRC stages (answered)": [n_prc],
                "ERC stages (answered)": [n_erc], "Furnaces (answered)": [n_furnace],
                "CGC stages kept": cgc_stages, "PRC stages kept": prc_stages,
                "ERC stages kept": erc_stages, "Furnaces kept": [f"F{n}" for n in furnaces],
            }
            st.toast("🎯 PI mapping generated!", icon="⚡")

        mapping = st.session_state["generated_pi_mapping"]
        if not mapping.empty:
            # m1, m2, m3 = st.columns(3)
            # m1.metric("Tags in generated mapping", len(mapping))
            # m2.metric("Tags excluded by line-up", len(pi_master) - len(mapping))
            # m3.metric("Tags matched in historian", len(st.session_state["generated_tags"]))

            # Clubbed section summary (tags grouped under CGC / PRC / ERC / Furnace ...)
            club_counts = mapping.groupby("Section").size().sort_values(ascending=False)
            club_chips = "  ".join(
                f'<span class="wizard-chip">{sec}: {cnt} tags</span>'
                for sec, cnt in club_counts.items()
            )
            st.markdown(f"**Clubbed by section →** {club_chips}", unsafe_allow_html=True)

            # with st.expander("🔎 Preview generated PI mapping (grouped by section)",
            #                  expanded=False):
            #     preview = mapping.sort_values(
            #         ["Section", "Generalized Description"]).reset_index(drop=True)
            #     sec_pick = st.selectbox(
            #         "Filter preview by section",
            #         options=["All"] + sorted(mapping["Section"].dropna().unique().tolist()),
            #         key="wiz_preview_section",
            #     )
            #     if sec_pick != "All":
            #         preview = preview[preview["Section"] == sec_pick].reset_index(drop=True)
            #     st.dataframe(preview, **FULL_WIDTH, height=320)
              
            
            
            
            
            with st.expander(
                "🔎 Preview generated PI mapping (grouped by section)",
                expanded=False
            ):
            
                preview = mapping.sort_values(
                    ["Section", "Generalized Description"]
                ).reset_index(drop=True)
            
            
                sec_pick = st.selectbox(
                    "Filter preview by section",
                    options=[
                        "All"
                    ] + sorted(mapping["Section"].dropna().unique().tolist()),
                    key="wiz_preview_section",
                )
            
            
                if sec_pick != "All":
                    preview = preview[
                        preview["Section"] == sec_pick
                    ].reset_index(drop=True)


                # Pi_tags column is intentionally kept EMPTY in the preview —
                # the plant team fills in the raw PI tags manually (or via the
                # uploaded config file later)
                if "Pi_tags" in preview.columns:
                    preview["Pi_tags"] = ""
            
            
                # Editable dropdown configuration
                preview_cfg = {}
            
                if "Pi_tags" in preview.columns:
                    preview_cfg["Pi_tags"] = st.column_config.TextColumn(
                        "Pi_tags",
                        help="Edit PI tag identifier"
                    )
            
            
                if "Generalized Description" in preview.columns:
                    preview_cfg["Generalized Description"] = st.column_config.TextColumn(
                        "Generalized Description",
                        help="Edit parameter description"
                    )
            
            
                if "Section" in preview.columns:
                    preview_cfg["Section"] = st.column_config.SelectboxColumn(
                        "Section",
                        options=[
                            "",
                            "CGC",
                            "PRC",
                            "ERC",
                            "Furnace",
                            "Quench",
                            "Cold"
                        ],
                        help="Select section"
                    )
            
            
                # Editable preview table
                edited_preview = st.data_editor(
                    preview,
                    column_config=preview_cfg,
                    key="wiz_editable_preview",
                    use_container_width=True,
                    height=320,
                    num_rows="dynamic"
                )
            
            
                # Apply changes
                if st.button(
                    "💾 Update Generated Mapping",
                    key="update_generated_mapping"
                ):
            
                    mapping = edited_preview.copy()
            
                    st.session_state["pi_mapping"] = mapping
            
                    st.success(
                        "Generated PI mapping updated successfully!"
                    )
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            # ---------------- Mapping export ----------------
            exp1, exp2 = st.columns(2)
            with exp1:
                def _sheet_or_placeholder_wiz(d):
                    return d if (d is not None and not d.empty) else pd.DataFrame([{"Equipment": None, "Selected": None}])
                map_buf = io.BytesIO()
                try:
                    with pd.ExcelWriter(map_buf, engine="openpyxl") as writer:
                        mapping.to_excel(writer, sheet_name=PI_SHEET, index=False)
                        sel_df = pd.DataFrame(
                            [(k, ", ".join(map(str, v))) for k, v in
                             st.session_state["wizard_selection"].items()],
                            columns=["Equipment", "Selected"],
                        )
                        _sheet_or_placeholder_wiz(sel_df).to_excel(writer, sheet_name="Plant_lineup", index=False)
                    st.download_button(
                        "📥 Export mapping (.xlsx)",
                        data=map_buf.getvalue(),
                        file_name="Generated_PI_mapping.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        **FULL_WIDTH,
                    )
                except Exception as e:  # noqa: BLE001
                    st.error(f"Mapping export failed: {e}")
            with exp2:
                st.download_button(
                    "📥 Export mapping (.csv)",
                    data=mapping.to_csv(index=False).encode("utf-8"),
                    file_name="Generated_PI_mapping.csv",
                    mime="text/csv",
                    **FULL_WIDTH,
                )
    st.markdown('</div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------
    # -----------------------------------------------------------------
    # 2.2b  TRAINING DATASETS — upload PI data sheet + Furnace data
    #       (required by the model development script). Saved to disk as
    #       ../Data/DMC_Screen_tags_data.xlsx with the two sheet names
    #       the script expects: "PI data" and "Furnace data".
    # -----------------------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📤 Step A — Upload Training Dataset")
    st.caption("Upload **DMC_Screen_tags_data.xlsx** — a single workbook that "
               "contains BOTH the **'PI data'** and **'Furnace data'** sheets. "
               "It is used to train the models.")

    dmc_upload = st.file_uploader(
        "📊 DMC_Screen_tags_data.xlsx (must contain 'PI data' + 'Furnace data' sheets)",
        type=["xlsx", "xls"], key="dmc_workbook_uploader",
        help="The workbook is saved to the Data folder as-is; the training "
             "script reads the 'PI data' and 'Furnace data' sheets from it.",
    )

    _workbook_on_disk = os.path.isfile(TRAIN_WORKBOOK)
    if _workbook_on_disk and dmc_upload is None:
        st.session_state["training_data_ready"] = True
        st.info(f"📄 Training workbook already on disk: `{TRAIN_WORKBOOK}` — "
                "upload a new file above only if you want to replace it.")

    if dmc_upload is not None:
        try:
            _xl = pd.ExcelFile(dmc_upload)
            _missing_sheets = [s for s in ("PI data", "Furnace data")
                               if s not in _xl.sheet_names]
            if _missing_sheets:
                st.error("🚨 The uploaded workbook is missing required sheet(s): "
                         + ", ".join(f"**{s}**" for s in _missing_sheets)
                         + f". Found sheets: {', '.join(_xl.sheet_names)}")
            else:
                st.success("✅ Workbook contains both required sheets: "
                           "'PI data' and 'Furnace data'.")
                if st.button("💾 Save training dataset to Data folder", **FULL_WIDTH):
                    os.makedirs(TRAIN_DATA_DIR, exist_ok=True)
                    # Save the raw uploaded bytes so ALL sheets are preserved
                    with open(TRAIN_WORKBOOK, "wb") as _f:
                        _f.write(dmc_upload.getvalue())
                    st.session_state["training_data_ready"] = True
                    st.success(f"✅ Training workbook saved: `{TRAIN_WORKBOOK}`")
        except Exception as save_err:  # noqa: BLE001
            st.error(f"Failed to read/save the training workbook: {save_err}")

    # -----------------------------------------------------------------
    # 2.3  Configuration editors — ONLY the two sheets required in the UI
    # -----------------------------------------------------------------
    def _apply_editor_delta(base_df: pd.DataFrame, delta: dict,
                            new_row_template: dict | None = None) -> pd.DataFrame:
        """Safely replays a st.data_editor delta onto a session DataFrame."""
        out = base_df.copy()
        try:
            if delta.get("deleted_rows"):
                keep = [i for i in range(len(out)) if i not in set(delta["deleted_rows"])]
                out = out.iloc[keep].reset_index(drop=True)
            for row in delta.get("added_rows", []):
                new_row = dict(new_row_template or {})
                new_row.update({k: v for k, v in row.items()
                                if k in out.columns or not out.columns.size})
                out = pd.concat([out, pd.DataFrame([new_row])], ignore_index=True)
            for idx, changes in (delta.get("edited_rows") or {}).items():
                idx = int(idx)
                if 0 <= idx < len(out):
                    for col, val in changes.items():
                        out.at[idx, col] = val
        except Exception:  # noqa: BLE001
            return base_df  # never corrupt config on a malformed delta
        return out

    def _simple_editor(state_key: str, editor_key: str, column_config: dict):
        """Editable grid whose edits commit straight to session state."""
        def _cb():
            delta = st.session_state.get(editor_key)
            if delta:
                st.session_state[state_key] = _apply_editor_delta(
                    st.session_state[state_key], delta)
        st.data_editor(
            st.session_state[state_key],
            column_config=column_config,
            **FULL_WIDTH,
            num_rows="dynamic",
            key=editor_key,
            on_change=_cb,
        )

    # -----------------------------------------------------------------
    # PI Tag Mapping is hidden on initial page load. It becomes visible
    # only after the user uploads a config workbook (above) that includes
    # the model mapping sheet.
    # -----------------------------------------------------------------
    _show_pi_tab = st.session_state.get("config_uploaded_via_ui", False)

    if _show_pi_tab:
        e_tab1, e_tab2 = st.tabs(["🏷️ PI Tag Mapping", "🧠 Model Mapping"])
    else:
        (e_tab2,) = st.tabs(["🧠 Model Mapping"])
        st.info("💡 The **PI Tag Mapping** sheet will appear here once you "
                "upload a config workbook (with the model mapping sheet) "
                "in the *Configuration Source* section above.")

    if _show_pi_tab:
        with e_tab1:
            st.caption(
                "Master PI dictionary (Pi_tags → Generalized Description → Section). "
                "Blank sections are auto-clubbed from tag names."
            )

            # NOTE: Pi_tags is NOT blanked here — this tab only appears after
            # a config workbook is uploaded, and the uploaded PI tag mapping
            # sheet must be shown with entries in ALL columns.

            pi_cfg = {
                "Pi_tags": st.column_config.TextColumn(
                    "Pi_tags",
                    help="Raw PI tag identifier"
                ),
                "Generalized Description": st.column_config.TextColumn(
                    "Generalized Description",
                    help="Human-readable parameter name"
                ),
                "Section": st.column_config.TextColumn(
                    "Section",
                    help="Plant area (CGC / PRC / ERC / Furnace / Quench / Cold)"
                ),
            }

            _simple_editor(
                "pi_names_df",
                f"ui_editor_pi_names_r{st.session_state['editor_rev']}",
                {
                    k: v for k, v in pi_cfg.items()
                    if k in st.session_state["pi_names_df"].columns
                }
            )
    
    with e_tab2:
        st.caption(
            "Predicted parameter → model input parameters."
        )
        # Clear only model input columns, keep predicted parameter names.
        # NEVER blank after a config upload — the uploaded model mapping must
        # appear in full (predicted parameters + input parameters).
        if ("model_mapping_initialized" not in st.session_state
                and not st.session_state.get("config_uploaded_via_ui", False)):
            for col in st.session_state["model_details_df"].columns:
                # Clear only input parameter mapping columns
                if any(
                    k in col.lower()
                    for k in [
                        "input",
                        "tag",
                        "pi_tags",
                        "source"
                    ]
                ):
                    st.session_state["model_details_df"][col] = ""
            st.session_state["model_mapping_initialized"] = True
        model_cfg = {}
        for col in st.session_state["model_details_df"].columns:
            # Predicted parameter should be read-only
            if "predicted" in col.lower():
    
                model_cfg[col] = st.column_config.TextColumn(
                    col,
                    disabled=True,
                    help="Predicted parameter from model"
                )
            # Input mapping should be selectable
            elif any(
                k in col.lower()
                for k in [
                    "input",
                    "tag",
                    "pi_tags",
                    "source"
                ]
            ):
                model_cfg[col] = st.column_config.SelectboxColumn(
                    col,
                    options=[""] + tag_options,
                    help=f"Select process tag for {col}"
                )
        _simple_editor(
            "model_details_df",
            f"ui_editor_model_details_r{st.session_state['editor_rev']}",
            model_cfg
        )
    
    # -----------------------------------------------------------------
    # 2.4  Config file generation — TWO sheets only:
    #      1) PI tag mapping (wizard-generated line-up if available,
    #         otherwise the full dictionary)
    #      2) Model mapping
    # -----------------------------------------------------------------
    # st.markdown("<br>", unsafe_allow_html=True)

    def _sheet_or_placeholder(sheet_df: pd.DataFrame) -> pd.DataFrame:
        """pandas 3.x + openpyxl cannot write a 0-row sheet; pad one blank row."""
        if sheet_df is None or sheet_df.empty:
            cols = (list(sheet_df.columns)
                    if sheet_df is not None and len(sheet_df.columns) else ["_"])
            return pd.DataFrame([{c: None for c in cols}])
        return sheet_df

    _gen_map = st.session_state["generated_pi_mapping"]
    pi_sheet_out = _gen_map if not _gen_map.empty else st.session_state["pi_names_df"]
    pi_sheet_label = ("wizard-generated line-up" if not _gen_map.empty
                      else "full dictionary (run the wizard to filter it)")
    
    config_buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(config_buffer, engine="openpyxl") as writer:
            _sheet_or_placeholder(pi_sheet_out).to_excel(
                writer, sheet_name=PI_SHEET, index=False)
            _sheet_or_placeholder(st.session_state["model_details_df"]).to_excel(
                writer, sheet_name="Model details", index=False)
        st.download_button(
            f"📥 Generate config file — 2 sheets: PI tag mapping ({pi_sheet_label}) + Model mapping",
            data=config_buffer.getvalue(),
            file_name="Config_file.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            **FULL_WIDTH,
        )
    except Exception as export_error:  # noqa: BLE001
        st.error(f"Failed to generate the configuration workbook: {export_error}")

    # -----------------------------------------------------------------
    # 2.45  MODEL TRAINING — after the model mapping sheet is filled,
    #       run Model_development_and_static_whatif_testing.py, which
    #       trains the models and saves the .pkl files into the Model
    #       folder (../Results/Model). Proceeding to the What-if
    #       Dashboard is unlocked only after this succeeds.
    # -----------------------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 🧠 Step B — Train Models")
    st.caption("Runs `Model_development_and_static_whatif_testing.py` on the "
               "saved training dataset + the model mapping sheet above, and "
               f"stores the model .pkl files in `{MODEL_DIR}`.")

    # ------------------------------------------------------------
    # Training is REQUIRED only when Raw_data_plus_simulated_data.xlsx
    # is absent from the Results folder. If it is present, models were
    # already trained -> skip training (retraining remains optional).
    # ------------------------------------------------------------
    _results_ready = os.path.isfile(RAW_SIM_FILE)
    _model_pkls = sorted(glob(os.path.join(MODEL_DIR, "*.pkl")))
    if _results_ready:
        st.session_state["models_trained"] = True

    _model_mapping_filled = not st.session_state["model_details_df"].dropna(how="all").empty
    _train_blockers = []
    if not os.path.isfile(MODEL_SCRIPT):
        _train_blockers.append(f"`Model_development_and_static_whatif_testing.py` "
                               f"not found next to this app (`{APP_DIR}`)")
    if not st.session_state["training_data_ready"]:
        _train_blockers.append("training dataset not saved yet (Step A above)")
    if not _model_mapping_filled:
        _train_blockers.append("the **🧠 Model Mapping** sheet is still empty")

    if _results_ready:
        st.success(f"✅ **Trained results found** — `Raw_data_plus_simulated_data.xlsx` "
                   f"is present in `{RESULTS_DIR}` "
                   f"({len(_model_pkls)} model .pkl file(s) in the Model folder). "
                   "Training is **not required** — you can proceed directly, "
                   "or retrain below if you want fresh models.")
        if _train_blockers:
            st.caption("ℹ️ To *retrain*, first resolve: " + " · ".join(_train_blockers))
        _train_btn_label = "🔁 Retrain models (optional) & refresh .pkl files"
    else:
        if _train_blockers:
            st.warning("⚠️ Before training, resolve: " + " · ".join(_train_blockers))
        _train_btn_label = "🧠 Train models & save .pkl files to Model folder"

    t_col1, t_col2 = st.columns([2, 1])
    with t_col2:
        if st.session_state["models_trained"]:
            st.success(f"✅ Models ready ({len(_model_pkls)} .pkl file(s))")
        else:
            st.info("⏳ No trained models yet")

    with t_col1:
        if st.button(_train_btn_label,
                     disabled=bool(_train_blockers), **FULL_WIDTH):
            try:
                os.makedirs(MODEL_DIR, exist_ok=True)
                os.makedirs(TRAIN_DATA_DIR, exist_ok=True)

                # The training script reads Config_file.xlsx (Model details)
                # from ../Data — persist the CURRENT session config there so
                # the model mapping just filled in the UI is what gets used.
                # with pd.ExcelWriter(os.path.join(TRAIN_DATA_DIR, "Config_file.xlsx"),
                #                     engine="openpyxl") as _cw:
                #     _sheet_or_placeholder(pi_sheet_out).to_excel(
                #         _cw, sheet_name=PI_SHEET, index=False)
                #     _sheet_or_placeholder(st.session_state["model_details_df"]).to_excel(
                #         _cw, sheet_name="Model details", index=False)

                _env = os.environ.copy()
                _env["MPLBACKEND"] = "Agg"   # suppress plt.show() pop-ups

                with st.spinner("Training models — this can take several "
                                "minutes, please keep this tab open..."):
                    _proc = subprocess.run(
                        [sys.executable, MODEL_SCRIPT],
                        cwd=APP_DIR, env=_env,
                        capture_output=True, text=True,
                    )

                _model_pkls = sorted(glob(os.path.join(MODEL_DIR, "*.pkl")))
                _results_ready = os.path.isfile(RAW_SIM_FILE)
                if _proc.returncode == 0 and (_model_pkls or _results_ready):
                    st.session_state["models_trained"] = True
                    st.success(f"✅ Training finished — {len(_model_pkls)} "
                               f".pkl file(s) saved in `{MODEL_DIR}`.")
                    with st.expander("📄 Saved model files"):
                        for _p in _model_pkls:
                            st.markdown(f"- `{os.path.basename(_p)}`")
                    st.rerun()
                else:
                    st.session_state["models_trained"] = bool(_model_pkls or _results_ready)
                    st.error("🚨 Model training failed "
                             f"(exit code {_proc.returncode}). "
                             "See the log below.")
                    with st.expander("🔧 Training log (stdout / stderr)"):
                        st.code((_proc.stdout or "")[-8000:] or "<no stdout>")
                        st.code((_proc.stderr or "")[-8000:] or "<no stderr>")
            except Exception as train_err:  # noqa: BLE001
                st.error(f"🚨 Could not run the training script: {train_err}")
                with st.expander("🔧 Full technical traceback"):
                    st.code(traceback.format_exc())

    # -----------------------------------------------------------------
    # 2.5  Proceed gate — simulation overrides in the What-if Dashboard
    #      unlock only after the user confirms the case setup is done
    # -----------------------------------------------------------------
    st.markdown("<br>", unsafe_allow_html=True)
    # st.markdown('<div class="executive-card">', unsafe_allow_html=True)

    if st.session_state["setup_complete"]:
        st.success("✅ Case setup confirmed — the **📊 What-if Dashboard** tab is "
                   "unlocked. Open it to set simulation overrides.")
        if st.button("🔒 Lock dashboard & revise setup", **FULL_WIDTH):
            st.session_state["setup_complete"] = False
            st.rerun()
    else:
        _proceed_ready = st.session_state["models_trained"]
        if _proceed_ready:
            st.markdown("**Models are trained.** Confirm the case setup to unlock "
                        "the simulation overrides in the What-if Dashboard tab.")
        else:
            st.markdown("**Proceeding is locked** — no trained models were found. "
                        "Either place `Raw_data_plus_simulated_data.xlsx` in the "
                        "`Results` folder (training is then skipped), or complete "
                        "Step A (upload the training dataset), fill the model "
                        "mapping sheet, and run Step B (train models).")
        if st.button("🚀 Proceed to What-if Dashboard",
                     disabled=not _proceed_ready, **FULL_WIDTH):
            st.session_state["setup_complete"] = True
            st.toast("Setup confirmed — open the 📊 What-if Dashboard tab.", icon="🚀")
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# =====================================================================
# PART-3  |  TAB 2 : WHAT-IF DASHBOARD
# =====================================================================
with tab2:

    # -----------------------------------------------------------------
    # GATE: simulation overrides appear only after the user clicks
    # "🚀 Proceed to What-if Dashboard" in the What-if case setup tab.
    # st.stop() is safe here because this tab is the last block rendered.
    # -----------------------------------------------------------------
    if not st.session_state.get("setup_complete", False):
        st.info(
            "🔒 **Simulation overrides are locked.**\n\n"
            "Complete the **⚙️ What-if case setup** tab and click "
            "**🚀 Proceed to What-if Dashboard** there to unlock this page."
        )
        st.stop()

    user_inputs_df = st.session_state.get("user_inputs_df", pd.DataFrame())
    display_order_df = st.session_state.get("display_order_df", pd.DataFrame())
    generated_tags = st.session_state.get("generated_tags", [])

    # -----------------------------------------------------------------
    # 3.1  Parameter source resolution
    #      Priority: wizard-generated tags -> auto-loaded config sheet
    #                -> full historian dropdown fallback.
    #      Limits: config 'user inputs' sheet when available for a tag,
    #              otherwise historical min/max.
    # -----------------------------------------------------------------
    config_limits: dict = {}
    if {"Parameter", "Lower Limit", "Upper Limit"}.issubset(user_inputs_df.columns):
        _dl = user_inputs_df.copy()
        _dl["Parameter"] = _dl["Parameter"].astype(str).str.strip()
        _dl = _dl[_dl["Parameter"].str.lower() != "nan"]
        config_limits = (_dl.set_index("Parameter")
                         [["Lower Limit", "Upper Limit"]].to_dict("index"))

    def _limits_for(tags: list) -> dict:
        """Config-sheet limits first, historical min/max as fallback."""
        out = {}
        for tag in tags:
            cfg = config_limits.get(tag)
            lo = pd.to_numeric(pd.Series([cfg.get("Lower Limit")]), errors="coerce").iloc[0] if cfg else None
            hi = pd.to_numeric(pd.Series([cfg.get("Upper Limit")]), errors="coerce").iloc[0] if cfg else None
            if pd.notna(lo) and pd.notna(hi):
                out[tag] = {"Lower Limit": float(lo), "Upper Limit": float(hi)}
            elif tag in df.columns and pd.api.types.is_numeric_dtype(df[tag]):
                out[tag] = {"Lower Limit": float(df[tag].min()),
                            "Upper Limit": float(df[tag].max())}
            else:
                out[tag] = {"Lower Limit": 0.0, "Upper Limit": 1e6}
        return out

    limits_dict: dict = {}
    user_defined_input_tags: list = []

    if generated_tags:
        # --- Source A: GENERATED TAG SELECTION (Plant Configuration Wizard) ---
        st.markdown("#### ⚡ Tag Source: Wizard Mapping")
        user_defined_input_tags = st.multiselect(
            "Generated tags (from plant line-up)",
            options=sorted(generated_tags),
            default=[],
            help="Tags produced by the Plant Configuration Wizard that also exist "
                 "in the historian. Pick the ones you want to override.",
        )
        limits_dict = _limits_for(user_defined_input_tags)
        if not user_defined_input_tags:
            st.info("💡 A wizard-generated mapping is active. Pick tags from "
                    "**'Generated tags'** above — the simulation override "
                    "inputs will appear in the **left sidebar**.")

    elif config_limits:
        # --- Source B: auto-loaded config 'user inputs' sheet ---
        st.markdown("#### 📋 Tag Source: Config Sheet")
        user_defined_input_tags = list(config_limits.keys())
        limits_dict = _limits_for(user_defined_input_tags)

    else:
        # --- Source C: full historian dropdown fallback ---
        st.markdown("#### 🏷️ Dynamic Tag Selection")
        user_defined_input_tags = st.multiselect(
            "User defined inputs",
            options=tag_options,
            default=[],
            help="No configuration found. Select process tags from the complete "
                 "historian list to simulate scenarios manually.",
        )
        limits_dict = _limits_for(user_defined_input_tags)
        if not user_defined_input_tags:
            st.info("💡 **Quick Start:** answer the wizard questions in the "
                    "⚙️ What-if case setup tab, or choose metrics from "
                    "**'User defined inputs'** above — the simulation override "
                    "inputs will appear in the **left sidebar**.")

    # -----------------------------------------------------------------
    # 3.2  Timestamp selection (date -> snapshot)
    # -----------------------------------------------------------------
    sel_col1, sel_col2 = st.columns(2)
    with sel_col1:
        available_dates = sorted(pd.Series(df.index.date).unique())
        selected_date = st.selectbox(
            "Historical Target Date", available_dates,
            index=len(available_dates) - 1,  # default to most recent day
        )
    with sel_col2:
        day_stamps = sorted(df.index[df.index.date == selected_date])
        timestamp_options = [ts.strftime("%Y-%m-%d %H:%M:%S") for ts in day_stamps]
        selected_time_str = st.selectbox(
            "Process Snapshot Timestamp", timestamp_options,
            index=len(timestamp_options) - 1,
            key="timestamp_selector",
        )

    if not timestamp_options:
        st.warning("No historian snapshots available for the selected date.")
        st.stop()

    selected_time = pd.Timestamp(selected_time_str)

    # -----------------------------------------------------------------
    # 3.3  Baseline values at the selected snapshot
    # -----------------------------------------------------------------
    with st.expander("🔎 Baseline Process Values at Selected Timestamp", expanded=False):
        try:
            active_tags = ([t for t in user_defined_input_tags if t in df.columns]
                           or df.columns.tolist())
            baseline = df.loc[[selected_time], active_tags].T
            baseline.columns = ["Current Value"]
            baseline = baseline.apply(pd.to_numeric, errors="coerce").round(2)
            st.dataframe(baseline, **FULL_WIDTH, height=280)
        except KeyError:
            st.error("⚠️ Selected snapshot not found in the historian index.")

    # -----------------------------------------------------------------
    # 3.4  User override inputs (validated against limits)
    #      Rendered in the LEFT SIDEBAR. Tag selection stays in the
    #      main tab so it is clearly visible after proceeding.
    # -----------------------------------------------------------------
    user_inputs = []
    if user_defined_input_tags:
        st.sidebar.markdown("### 🔧 Simulation Overrides")
        st.sidebar.caption("Enter a target value to override — leave blank "
                           "to keep the actual (baseline) value.")

    for param in user_defined_input_tags:
        limits = limits_dict.get(param) or {}
        try:
            lower = float(limits.get("Lower Limit", 0.0))
        except (TypeError, ValueError):
            lower = 0.0
        try:
            upper = float(limits.get("Upper Limit", 1e6))
        except (TypeError, ValueError):
            upper = 1e6

        st.sidebar.markdown(f"**{param}**")
        st.sidebar.caption(f"Boundary range: {lower:,.2f} → {upper:,.2f}")

        raw = st.sidebar.text_input(
            "Override target value", value="", key=f"ovr_{param}",
            placeholder="blank = keep actual", label_visibility="collapsed",
        )

        val_float = np.nan
        if raw.strip():
            try:
                val_float = float(raw)
                if not (lower <= val_float <= upper):
                    st.sidebar.error(f"Value must be between {lower:,.2f} and {upper:,.2f}")
                    val_float = np.nan
            except ValueError:
                st.sidebar.error("Numeric input required")
                val_float = np.nan

        user_inputs.append({"Parameter": param, "Value": val_float})

    user_input_df = pd.DataFrame(user_inputs, columns=["Parameter", "Value"])
    n_overrides = int(user_input_df["Value"].notna().sum()) if not user_input_df.empty else 0

    # -----------------------------------------------------------------
    # 3.5  whatif_analysis execution
    # -----------------------------------------------------------------
    run_label = (f"🚀 Compute What-If Scenario  ({n_overrides} override"
                 f"{'s' if n_overrides != 1 else ''} active)")
    if st.button(run_label):
        if whatif_analysis is None:
            st.error("The what-if engine is unavailable (whatif_runner import failed).")
        else:
            with st.spinner("Processing operational scenario model rules..."):
                try:
                    st.session_state["result"] = whatif_analysis(df, selected_time, user_input_df)
                    st.session_state["selected_time"] = selected_time
                except Exception as run_err:  # noqa: BLE001
                    st.session_state.pop("result", None)
                    st.error(f"🚨 What-if analysis failed: {run_err}")
                    with st.expander("🔧 Full technical traceback"):
                        st.code(traceback.format_exc())

    # =====================================================================
    # PART-4  |  RESULTS : KPI CARDS, COMPARISON TABLE, VALIDATION, EXPORT
    # =====================================================================
    if "result" in st.session_state and st.session_state["result"] is not None:
        result = st.session_state["result"]
        selected_time_download = st.session_state.get("selected_time", selected_time)

        # Accept either a Styler or a plain DataFrame from the engine
        if _PdStyler is not None and isinstance(result, _PdStyler):
            result_df = result.data.copy()
        elif isinstance(result, pd.DataFrame):
            result_df = result.copy()
        else:
            st.error("The what-if engine returned an unsupported result type "
                     f"({type(result).__name__}). Expected DataFrame or Styler.")
            st.stop()

        result_df.drop(columns=["Timestamp"], errors="ignore", inplace=True)

        if {"actual", "estimated"}.issubset(result_df.index):
            result_df.loc["Change"] = (
                pd.to_numeric(result_df.loc["estimated"], errors="coerce")
                - pd.to_numeric(result_df.loc["actual"], errors="coerce")
            )
        else:
            st.warning("Result is missing 'actual'/'estimated' rows — "
                       "the Change row and KPI deltas cannot be computed.")

        transpose_df = result_df.T
        transpose_df = transpose_df[~transpose_df.index.duplicated(keep="first")]

        # Reporting order (falls back gracefully if no ordering configured)
        preferred_order = (
            display_order_df["Preferred columns"].dropna().tolist()
            if ("Preferred columns" in display_order_df.columns
                and not display_order_df.empty) else []
        )
        preferred_existing = [c for c in preferred_order if c in transpose_df.index]
        remaining = [c for c in transpose_df.index if c not in preferred_existing]
        transpose_df = transpose_df.loc[preferred_existing + remaining]

        # -----------------------------------------------------------------
        # 4.1  KPI cards
        # -----------------------------------------------------------------
        KPI_TAGS = [
            'DMCTF_feed', 'Quench_tower_overhead_temp', 'CGC_TURBINE_1_SPEED_(RPM)',
            'CGC_STAGE_1_SUCTION_PRESSURE', 'CGC_Power_KW', 'PRC_turbine_RPM',
            'PRC_1ST_STAGE_Suction_PRESSURE', 'PRC_Total_estimated_power_MW',
            'ERC_power', 'ERC_1ST_STAGE_Suction_PRESSURE', 'ERC_turbine_Speed',
            'Total_Power_(KW)', 'Total_required_steam_flow_(TPH)', 'Ethylene_product_flow',
        ]
        active_kpis = [t for t in KPI_TAGS if t in transpose_df.index]

        def render_kpi_card(kpi_tag: str):
            """Renders one executive KPI tile with a business-rule colour code."""
            try:
                act = float(transpose_df.at[kpi_tag, "actual"])
                est = float(transpose_df.at[kpi_tag, "estimated"])
                chg = float(transpose_df.at[kpi_tag, "Change"])
            except (KeyError, TypeError, ValueError):
                return
            if not (np.isfinite(act) and np.isfinite(est)):
                return

            if est < act:
                border, bg, txt = "#ef4444", "rgba(239,68,68,0.15)", "#f87171"
            elif est > act:
                border, bg, txt = "#10b981", "rgba(16,185,129,0.15)", "#34d399"
            else:
                border, bg, txt = "rgba(255,255,255,0.1)", "rgba(148,163,184,0.1)", "#94a3b8"

            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1e293b, #0f172a);
                border-left: 4px solid {border};
                border-top: 1px solid rgba(255,255,255,0.05);
                border-right: 1px solid rgba(255,255,255,0.05);
                border-bottom: 1px solid rgba(255,255,255,0.05);
                border-radius: 8px; padding: 16px; margin-bottom: 14px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                <div style="color:#94a3b8; font-size:11px; font-weight:600;
                            text-transform:uppercase; letter-spacing:.03em;
                            margin-bottom:6px; white-space:nowrap; overflow:hidden;
                            text-overflow:ellipsis;" title="{kpi_tag}">
                    🏷️ {kpi_tag.replace('_', ' ')}
                </div>
                <div class="kpi-value" style="color:#f8fafc; font-size:26px;
                            font-weight:800; line-height:1.2; margin-bottom:8px;">
                    {fmt_num(est)}
                </div>
                <div style="display:inline-block; padding:3px 8px; border-radius:4px;
                            font-size:15px; font-weight:700;
                            background-color:{bg}; color:{txt};">
                    {fmt_num(chg, force_sign=True)} vs Act ({fmt_num(act)})
                </div>
            </div>
            """, unsafe_allow_html=True)

        if active_kpis:
            st.markdown("#### 📊 Key Performance Indicators")
            for chunk in [active_kpis[i:i + 4] for i in range(0, len(active_kpis), 4)]:
                for col, kpi in zip(st.columns(len(chunk)), chunk):
                    with col:
                        render_kpi_card(kpi)

        # -----------------------------------------------------------------
        # 4.2  Actual vs Estimated table with Change highlighting
        # -----------------------------------------------------------------
        st.markdown('<br><h3>📈 Actual vs Estimated Scenario Output</h3>',
                    unsafe_allow_html=True)

        display_df = transpose_df.map(
            lambda x: f"{x:.2f}".rstrip("0").rstrip(".")
            if isinstance(x, (int, float, np.number)) and pd.notna(x) else x
        )

        def highlight_change_only(row):
            styles = []
            for col in row.index:
                if str(col).lower() == "change":
                    try:
                        v = float(row[col])
                    except (TypeError, ValueError):
                        styles.append("")
                        continue
                    if v < 0:
                        styles.append("color:#ef4444; font-weight:600; "
                                      "background-color:rgba(239,68,68,0.08);")
                    elif v > 0:
                        styles.append("color:#10b981; font-weight:600; "
                                      "background-color:rgba(16,185,129,0.08);")
                    else:
                        styles.append("color:#94a3b8; font-weight:500;")
                else:
                    styles.append("")
            return styles

        st.dataframe(display_df.style.apply(highlight_change_only, axis=1),
                     **FULL_WIDTH, height=480)

        # -----------------------------------------------------------------
        # 4.3  Scenario CSV export
        # -----------------------------------------------------------------
        download_df = display_df.copy().reset_index()
        download_df.rename(columns={"index": "Parameter"}, inplace=True)
        download_df.insert(0, "Selected Timestamp", str(selected_time_download))

        st.download_button(
            "📥 Export Baseline vs Simulation Matrix (.CSV)",
            data=download_df.to_csv(index=False).encode("utf-8"),
            file_name="WhatIf_Result.csv",
            mime="text/csv",
            **FULL_WIDTH,
        )

        # -----------------------------------------------------------------
        # 4.4  Historical validation filters + unified export
        # -----------------------------------------------------------------
        st.sidebar.markdown("### 🔍 Validation Filters")

        VALIDATION_TAGS = [
            'DMCTF_feed', 'Quench_tower_overhead_temp', 'Fresh_ethane_feed',
            'fresh_feed_ethane_content', 'CGC_STAGE_1_SUCTION_PRESSURE',
        ]
        available_val_tags = [c for c in VALIDATION_TAGS if c in df.columns]

        if not available_val_tags:
            st.error("Validation tags are missing from the historian dataset.")
        else:
            filter_values = {}
            for tag in available_val_tags:
                if pd.api.types.is_numeric_dtype(df[tag]):
                    g_min, g_max = float(df[tag].min()), float(df[tag].max())
                    st.sidebar.markdown(f"**Filter {tag}**")
                    f1, f2 = st.sidebar.columns(2)
                    with f1:
                        min_val = st.number_input("Min", value=g_min, key=f"{tag}_min")
                    with f2:
                        max_val = st.number_input("Max", value=g_max, key=f"{tag}_max")
                    filter_values[tag] = (min_val, max_val)
                else:
                    uniq = df[tag].dropna().unique().tolist()
                    filter_values[tag] = st.sidebar.multiselect(
                        f"Select {tag}", options=uniq, default=uniq)

            df_filtered = df.copy()
            for tag, criteria in filter_values.items():
                if pd.api.types.is_numeric_dtype(df_filtered[tag]):
                    lo, hi = criteria
                    df_filtered = df_filtered[
                        (df_filtered[tag] >= lo) & (df_filtered[tag] <= hi)]
                else:
                    df_filtered = df_filtered[df_filtered[tag].isin(criteria)]

            st.markdown('<br><h3>🔍 Correlated Historical Validation Sets</h3>',
                        unsafe_allow_html=True)

            if df_filtered.empty:
                st.warning("No historical snapshots match the current validation "
                           "filters — widen the ranges in the sidebar.")
            else:
                col_pref = [c for c in preferred_order if c in df_filtered.columns]
                col_rest = [c for c in df_filtered.columns if c not in col_pref]
                df_filtered = df_filtered[col_pref + col_rest]

                df_display = df_filtered.map(
                    lambda x: f"{x:.2f}".rstrip("0").rstrip(".")
                    if isinstance(x, (int, float, np.number)) and pd.notna(x) else x
                ).T
                df_display.index.name = "Parameter"

                st.caption(f"{df_filtered.shape[0]} matching historical snapshot(s)")
                st.dataframe(df_display, **FULL_WIDTH)

                try:
                    combined_df = pd.merge(
                        download_df, df_display.reset_index(),
                        on="Parameter", how="inner")
                    st.download_button(
                        "📥 Export Unified Comparison & Historical Validation Data (.CSV)",
                        data=combined_df.to_csv(index=False).encode("utf-8"),
                        file_name="filtered_validation_data.csv",
                        mime="text/csv",
                        **FULL_WIDTH,
                    )
                except Exception as merge_err:  # noqa: BLE001
                    st.error(f"Could not build the unified export: {merge_err}")