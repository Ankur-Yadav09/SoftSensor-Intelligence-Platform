"""
src/whatif/engine.py
======================
Ported, Streamlit-free version of Scripts/whatif_runner.py's whatif_analysis()
pipeline. Scripts/ itself is never imported or edited — this is an independent
reimplementation that preserves the exact math, step order, and mid-pipeline
constraint short-circuit of the original.

Differences from the original, all deliberate (see the migration plan):
  - No module-level import-time side effect (the original called
    load_process_data() at import time); the historian is loaded once by the
    caller (backend/app/services/what_if_service.py) and passed in.
  - Config (Model details, Constraints) is loaded once by the caller via
    src/whatif/config_io.py and passed in, instead of being re-read from
    Config_file.xlsx on every call.
  - Paths are parameterized (model_dir) instead of hardcoded "..\\Results\\Model".
  - Returns a plain WhatIfResult dataclass instead of a pandas Styler —
    coloring is a frontend concern.
  - The "Actual_vs_estimated what if.xlsx" disk write is strictly opt-in via
    write_actual_vs_estimated_xlsx (default False), and when enabled writes to
    a per-request filename rather than the original's fixed name, to avoid
    concurrent-request overwrites.

The pipeline is intentionally NOT decomposed into per-tag functions callable
independently over HTTP: later steps consume earlier results (e.g.
Delta_CGC_Suction_Pressure computed mid-pipeline feeds the later COT formula),
and there is a hard mid-pipeline short-circuit on CGC_5TH_STG_DISCH_PRES. One
call to whatif_analysis() is one full, order-dependent pipeline run.
"""
from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from CoolProp.CoolProp import PropsSI
from scipy.optimize import minimize_scalar

from src.whatif.config_io import CONSTRAINTS_MAX_COL, WhatIfConfig


@dataclass
class WhatIfResult:
    actual: dict
    estimated: dict
    constraint_hit: bool
    constraint_message: str | None = None


# ---------------------------------------------------------------------------
# Per-tag Kalman prediction / user-override helpers
# ---------------------------------------------------------------------------

def _predict_and_update_with_kalman(
    y_col: str,
    row_df: pd.DataFrame,
    model_details_df: pd.DataFrame,
    model_dir: str,
) -> pd.DataFrame:
    """Loads kalman_filter_model_{y_col}.pkl + its two scalers, runs one
    no-measurement Kalman step over the tag's configured input features, and
    writes the inverse-scaled prediction into row_df[y_col]."""
    u_cols_row = model_details_df[model_details_df["Predicted parameter"] == y_col]
    u_cols_row = u_cols_row.dropna(axis=1)
    u_cols = u_cols_row.iloc[:, 1:].values.ravel().tolist()

    model_path = os.path.join(model_dir, f"kalman_filter_model_{y_col}.pkl")
    scaler_x_path = os.path.join(model_dir, f"scaler_X_{y_col}.pkl")
    scaler_y_path = os.path.join(model_dir, f"scaler_y_{y_col}.pkl")

    with open(model_path, "rb") as f:
        kalman_model = pickle.load(f)
    scaler_x = joblib.load(scaler_x_path)
    scaler_y = joblib.load(scaler_y_path)

    feature_df = row_df[u_cols]
    scaled = scaler_x.transform(feature_df)
    kalman_model.step(y=None, u=scaled.reshape(-1, 1))

    results = kalman_model.to_dataframe()
    pred_scaled = results[("$y_0$", "filtered", "output")].iloc[-1]
    pred_unscaled = scaler_y.inverse_transform([[pred_scaled]]).ravel()

    row_df.loc[:, y_col] = pred_unscaled[0]
    return row_df


def _update_parameter_from_user_input(
    y_col: str,
    user_input_df: pd.DataFrame,
    row_df: pd.DataFrame,
) -> pd.DataFrame:
    """Overwrites row_df[y_col] with the user-supplied override if present and
    numeric; otherwise leaves the current (baseline/predicted) value."""
    matching = user_input_df.loc[user_input_df["Parameter"].str.strip() == y_col, "Value"]
    raw_val = matching.iloc[0] if not matching.empty else np.nan
    try:
        user_value = float(raw_val) if pd.notna(raw_val) else np.nan
    except (ValueError, TypeError):
        user_value = np.nan

    current_series = row_df.get(y_col, np.nan)
    current_value = (
        current_series.iloc[0]
        if isinstance(current_series, pd.Series) and not current_series.empty
        else current_series
    )

    final_value = user_value if not np.isnan(user_value) else current_value
    row_df.loc[:, y_col] = final_value
    return row_df


# ---------------------------------------------------------------------------
# COT (Coil Outlet Temperature) calculation chain
# ---------------------------------------------------------------------------

def _cot_calculation(df_furnace: pd.DataFrame) -> pd.DataFrame:
    df_furnace["Plant_average_feed_rate_Coil"] = df_furnace["DMCTF_feed"] / (
        df_furnace["Number_Of_Furnaces_Online"] * 4
    )

    df_furnace["Coil_CIP_Calculated"] = (
        -131.3081
        + (0.0755 * df_furnace["Plant_average_feed_rate_Coil"])
        + (0.1463 * df_furnace["Ethane_Feed_Preheater_Ethane_Feed_Outlet_Pressure"])
        + (0.6819 * df_furnace["Furnace_Ethane_Feed_Preheater_Ethane_Feed_Outlet_Temperature"])
        + (0.4853 * df_furnace["Coil_Weighted_Avg_Feed_CV_opening"])
        + (0.8766 * df_furnace["Coil_Weighted_Avg_Steam_CV_opening"])
    )

    df_furnace["Coil_Steam_Flow"] = df_furnace["Coil_Avg_SHC_Ratio"] * df_furnace["Plant_average_feed_rate_Coil"]

    df_furnace["Coil_Mixed_Feed_flow"] = df_furnace["Coil_Steam_Flow"] + df_furnace["Plant_average_feed_rate_Coil"]

    df_furnace["Coil_Mixed_Feed_Cp"] = (
        (df_furnace["Coil_Steam_Flow"] * 2.067) + (df_furnace["Plant_average_feed_rate_Coil"] * 1.909)
    ) / (df_furnace["Coil_Steam_Flow"] + df_furnace["Plant_average_feed_rate_Coil"])

    df_furnace["Coil_Mixed_Feed_Mol_wt"] = df_furnace["Coil_Mixed_Feed_flow"] / (
        (df_furnace["Plant_average_feed_rate_Coil"] / df_furnace["Furnace_Feed_Average_Molecular_Wt"])
        + (df_furnace["Coil_Steam_Flow"] / 18.0)
    )

    df_furnace["Coil_Volumetric_Flow"] = df_furnace["Coil_Mixed_Feed_flow"] / (
        ((df_furnace["Coil_CIP_Calculated"] + 101.325) * 0.00982963 * df_furnace["Coil_Mixed_Feed_Mol_wt"])
        / (0.08206 * (df_furnace["Coil_Weighted_Avg_Coil_Mixed_Feed_Inlet_Temperature"] + 273.15))
    )

    df_furnace["Coil_CIP_Corrected_atma"] = np.where(
        (df_furnace["Coil_CIP_Calculated"] / 101.325 + 1) < 5,
        (df_furnace["Coil_CIP_Calculated"] / 101.325 + 1)
        - (df_furnace["Coil_Volumetric_Flow"] * 144 / 1309.83) * 0.00986923,
        (df_furnace["Coil_CIP_Calculated"] / 101.325 + 1)
        - (df_furnace["Coil_Volumetric_Flow"] * 131 / 1209.52) * 0.00986923,
    )
    return df_furnace


# ---------------------------------------------------------------------------
# PRC (Propylene Refrigeration Compressor) section: power + turbine matching
# ---------------------------------------------------------------------------

def _prc_section_power(df: pd.DataFrame) -> pd.DataFrame:
    eta = 0.70  # assumed compressor efficiency

    density_1st, vol_flow_1st = [], []
    for i in range(len(df)):
        t_k = df["PRC_1ST_STAGE_Suction_TEMP"].iloc[i] + 273.15
        p_pa = df["PRC_1ST_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5
        rho = PropsSI("D", "T", t_k, "P", p_pa, "Propylene")
        vol_flow_1st.append(df["PRC_1ST_STAGE_Suction_FLOW"].iloc[i] * 1000 / rho)
        density_1st.append(rho)
    df["PRC_Density_1st_stage"] = density_1st
    df["PRC VOL FLOW 1ST STAGE"] = vol_flow_1st

    density_2nd, vol_flow_2nd = [], []
    for i in range(len(df)):
        t_k = df["PRC_2nd_stage_drum_Overhead_Temp"].iloc[i] + 273.15
        p_pa = df["PRC_2ND_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5
        rho = PropsSI("D", "T", t_k, "P", p_pa, "Propylene")
        vol_flow_2nd.append(
            (df["PRC_1ST_STAGE_Suction_FLOW"].iloc[i] + df["PRC_2nd_stage_drum_Overhead_Flow"].iloc[i]) * 1000 / rho
        )
        density_2nd.append(rho)
    df["PRC_Density_2nd_stage"] = density_2nd
    df["PRC VOL FLOW 2ND STAGE"] = vol_flow_2nd

    density_3rd, vol_flow_3rd = [], []
    for i in range(len(df)):
        t_k = df["PRC_3RD_STAGE_Suction_TEMP"].iloc[i] + 273.15
        p_pa = df["PRC_3RD_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5
        rho = PropsSI("D", "T", t_k, "P", p_pa, "Propylene")
        vol_flow_3rd.append(df["PRC_3RD_STAGE_Suction_FLOW"].iloc[i] * 1000 / rho)
        density_3rd.append(rho)
    df["PRC_Density_3rd_stage"] = density_3rd
    df["PRC VOL FLOW 3RD STAGE"] = vol_flow_3rd

    power_1st = []
    for i in range(len(df)):
        h1 = PropsSI("H", "T", df["PRC_1ST_STAGE_Suction_TEMP"].iloc[i] + 273.15, "P",
                     df["PRC_1ST_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5, "Propylene")
        s1 = PropsSI("S", "T", df["PRC_1ST_STAGE_Suction_TEMP"].iloc[i] + 273.15, "P",
                     df["PRC_1ST_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5, "Propylene")
        h2s = PropsSI("H", "P", df["PRC_1ST_STAGE_Discharge_PRESSURE"].iloc[i] * 1000 + 1e5, "S", s1, "Propylene")
        h2 = h1 + (h2s - h1) / eta
        power_1st.append(((df["PRC_1ST_STAGE_Suction_FLOW"].iloc[i] * 1000) / 3600) * (h2 - h1) / 1e6)
    df["PRC_1st_stage_comp_estimated_power_MW"] = power_1st

    power_2nd = []
    for i in range(len(df)):
        h1 = PropsSI("H", "T", df["PRC_2nd_stage_drum_Overhead_Temp"].iloc[i] + 273.15, "P",
                     df["PRC_2ND_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5, "Propylene")
        s1 = PropsSI("S", "T", df["PRC_2nd_stage_drum_Overhead_Temp"].iloc[i] + 273.15, "P",
                     df["PRC_2ND_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5, "Propylene")
        h2s = PropsSI("H", "P", df["PRC_3RD_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5, "S", s1, "Propylene")
        h2 = h1 + (h2s - h1) / eta
        power_2nd.append((
            ((df["PRC_2nd_stage_drum_Overhead_Flow"].iloc[i] + df["PRC_1ST_STAGE_Suction_FLOW"].iloc[i]) * 1000)
            / 3600
        ) * (h2 - h1) / 1e6)
    df["PRC_2nd_stage_comp_estimated_power_MW"] = power_2nd

    power_3rd = []
    for i in range(len(df)):
        h1 = PropsSI("H", "T", df["PRC_3RD_STAGE_Suction_TEMP"].iloc[i] + 273.15, "P",
                     df["PRC_3RD_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5, "Propylene")
        s1 = PropsSI("S", "T", df["PRC_3RD_STAGE_Suction_TEMP"].iloc[i] + 273.15, "P",
                     df["PRC_3RD_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5, "Propylene")
        h2s = PropsSI("H", "P", df["PRC_3RD_STAGE_Discharge_PRESSURE"].iloc[i] * 1000 + 1e5, "S", s1, "Propylene")
        h2 = h1 + (h2s - h1) / eta
        power_3rd.append(((df["PRC_3RD_STAGE_Suction_FLOW"].iloc[i] * 1000) / 3600) * (h2 - h1) / 1e6)
    df["PRC_3rd_stage_comp_estimated_power_MW"] = power_3rd

    df["PRC_Total_estimated_power_MW"] = (
        df["PRC_1st_stage_comp_estimated_power_MW"]
        + df["PRC_2nd_stage_comp_estimated_power_MW"]
        + df["PRC_3rd_stage_comp_estimated_power_MW"]
    )
    return df


def _isentropic_enthalpy(p_target: float, s_in: float) -> float:
    s_f = PropsSI("S", "P", p_target, "Q", 0, "Water") / 1000
    s_g = PropsSI("S", "P", p_target, "Q", 1, "Water") / 1000
    if s_f < s_in < s_g:
        x = (s_in - s_f) / (s_g - s_f)
        h_f = PropsSI("H", "P", p_target, "Q", 0, "Water")
        h_g = PropsSI("H", "P", p_target, "Q", 1, "Water")
        h_iso = h_f + x * (h_g - h_f)
    else:
        h_iso = PropsSI("H", "P", p_target, "S", s_in, "Water")
    return h_iso / 1000


def _match_actual_power(row: pd.Series) -> tuple:
    try:
        p_steam = row["PRC_turbine_Steam_pressure"] * 1000
        t_steam = row["PRC_turbine_Steam_Temp"] + 273.15
        h_steam = PropsSI("H", "P", p_steam, "T", t_steam, "Water") / 1000

        pe = row["PRC_turbine_Extraction_Pressure"] * 1000
        t_sat_extraction = PropsSI("T", "P", pe, "Q", 1, "Water")
        he = PropsSI("H", "P", pe, "T", t_sat_extraction + 0.01, "Water") / 1000

        pc = row["PRC_turbine_Condensate_Pressure"] * 1000
        t_sat_condensate = PropsSI("T", "P", pc, "Q", 0, "Water")
        hc_liquid = PropsSI("H", "P", pc, "T", t_sat_condensate - 0.01, "Water") / 1000
        dryness_fraction = 0.92
        hc_vapor = PropsSI("H", "P", pc, "T", t_sat_condensate + 0.01, "Water") / 1000
        hc = hc_liquid + hc_vapor * dryness_fraction

        condensate_flow_tph = row["PRC_turbine_condensate_flow"]
        condensate_flow_kg_hr = condensate_flow_tph * 1000
        actual_power = row["PRC_Total_estimated_power_MW"]

        def objective(extraction_flow_tph: float) -> float:
            extraction_flow_kg_hr = extraction_flow_tph * 1000
            power = (
                (extraction_flow_kg_hr * (h_steam - he)) + (condensate_flow_kg_hr * (h_steam - hc))
            ) / 3600 / 1000
            return (power - actual_power) ** 2

        result = minimize_scalar(objective, bounds=(10, 350), method="bounded")

        if result.success:
            ef_opt = result.x
            ef_kg_hr = ef_opt * 1000
            sf_opt = ef_opt + condensate_flow_tph
            sf_kg_hr = sf_opt * 1000
            power_matched_ee = ((ef_kg_hr * (h_steam - he)) + (condensate_flow_kg_hr * (h_steam - hc))) / 3600 / 1000
            h2_actual = (ef_kg_hr * he + condensate_flow_kg_hr * hc) / sf_kg_hr
            power_matched_sf = (h_steam - h2_actual) * (sf_kg_hr / 3600 / 1000)
            return ef_opt, sf_opt, power_matched_ee, power_matched_sf, h2_actual

        return (
            row["PRC_turbine_Extraction_flow"], row["PRC_turbine_steam_flow"],
            row["PRC_turbine_current_Turbine_power_MW_based_on_EE"],
            row["PRC_turbine_current_Turbine_power_MW_based_on_steam_flow"], None,
        )
    except Exception:
        return (
            row["PRC_turbine_Extraction_flow"], row["PRC_turbine_steam_flow"],
            row["PRC_turbine_current_Turbine_power_MW_based_on_EE"],
            row["PRC_turbine_current_Turbine_power_MW_based_on_steam_flow"], None,
        )


def _prc_turbine_extraction_steam_flow_prediction(df: pd.DataFrame) -> pd.DataFrame:
    steam_enth, steam_entr, out_enth, out_isen_enth = [], [], [], []
    power_ext, power_exh, power_ee, power_sf, spec_steam = [], [], [], [], []

    for i in range(len(df)):
        steam_flow_tph = df["PRC_turbine_steam_flow"].iloc[i]
        condensate_flow_tph = df["PRC_turbine_condensate_flow"].iloc[i]
        extraction_flow_tph = df["PRC_turbine_Extraction_flow"].iloc[i]

        steam_flow_kg_hr = steam_flow_tph * 1000
        extraction_flow_kg_hr = extraction_flow_tph * 1000
        condensate_flow_kg_hr = condensate_flow_tph * 1000

        p_steam = df["PRC_turbine_Steam_pressure"].iloc[i] * 1000
        t_steam = df["PRC_turbine_Steam_Temp"].iloc[i] + 273.15

        pe = df["PRC_turbine_Extraction_Pressure"].iloc[i] * 1000
        t_sat_extraction = PropsSI("T", "P", pe, "Q", 1, "Water")

        pc = df["PRC_turbine_Condensate_Pressure"].iloc[i] * 1000
        t_sat_condensate = PropsSI("T", "P", pc, "Q", 0, "Water")

        h_steam = PropsSI("H", "P", p_steam, "T", t_steam, "Water") / 1000
        s_steam = PropsSI("S", "P", p_steam, "T", t_steam, "Water") / 1000

        he = PropsSI("H", "P", pe, "T", t_sat_extraction + 0.01, "Water") / 1000
        hc_liquid = PropsSI("H", "P", pc, "T", t_sat_condensate - 0.01, "Water") / 1000
        dryness_fraction = 0.92
        hc_vapor = PropsSI("H", "P", pc, "T", t_sat_condensate + 0.01, "Water") / 1000
        hc = hc_liquid + hc_vapor * dryness_fraction

        power_gen_extraction = extraction_flow_kg_hr * (h_steam - he) / 3600 / 1000
        power_gen_exhaust = condensate_flow_kg_hr * (h_steam - hc) / 3600 / 1000
        turbine_power_mw_ee = power_gen_extraction + power_gen_exhaust
        specific_steam_consumption = steam_flow_tph / turbine_power_mw_ee

        he_s = _isentropic_enthalpy(pe, s_steam)
        hc_s = _isentropic_enthalpy(pc, s_steam)

        h2_actual = (extraction_flow_kg_hr * he + condensate_flow_kg_hr * hc) / steam_flow_kg_hr
        h2s_ideal = (extraction_flow_kg_hr * he_s + condensate_flow_kg_hr * hc_s) / steam_flow_kg_hr

        turbine_power_mw_sf = (h_steam - h2_actual) * (steam_flow_kg_hr / (3600 * 1000))

        steam_enth.append(h_steam)
        steam_entr.append(s_steam)
        out_enth.append(h2_actual)
        out_isen_enth.append(h2s_ideal)
        power_ext.append(power_gen_extraction)
        power_exh.append(power_gen_exhaust)
        power_ee.append(turbine_power_mw_ee)
        power_sf.append(turbine_power_mw_sf)
        spec_steam.append(specific_steam_consumption)

    df["PRC_turbine_current_steam_enthalpy_KJ_Kg"] = steam_enth
    df["PRC_turbine_current_steam_entropy_KJ_KgK"] = steam_entr
    df["PRC_turbine_current_outlet_ethalpy_KJ_Kg"] = out_enth
    df["PRC_turbine_current_outlet_isentropic_ethalpy_KJ_Kg"] = out_isen_enth
    df["PRC_turbine_current_power_gen_extraction_MW"] = power_ext
    df["PRC_turbine_current_power_gen_exhaust_MW"] = power_exh
    df["PRC_turbine_current_Turbine_power_MW_based_on_EE"] = power_ee
    df["PRC_turbine_current_Turbine_power_MW_based_on_steam_flow"] = power_sf
    df["PRC_turbine_current_Specific_steam_consumption_MT_MW"] = spec_steam

    optimized_extraction, calculated_steam_flow = [], []
    matched_power_ee, matched_power_sf, matched_h2 = [], [], []
    for _, row in df.iterrows():
        ef, sf, p_ee, p_sf, h2 = _match_actual_power(row)
        optimized_extraction.append(ef)
        calculated_steam_flow.append(sf)
        matched_power_ee.append(p_ee)
        matched_power_sf.append(p_sf)
        matched_h2.append(h2)

    df["PRC_turbine_Optimized_Extraction_flow_TPH"] = optimized_extraction
    df["PRC_turbine_Calculated_Steam_flow_TPH"] = calculated_steam_flow
    df["PRC_turbine_Matched_Turbine_power_MW_EE"] = matched_power_ee
    df["PRC_turbine_Matched_Turbine_power_MW_SF"] = matched_power_sf
    df["PRC_turbine_Matched_h2_actual_KJ_Kg"] = matched_h2
    df["Power_Error"] = df["PRC_turbine_Matched_Turbine_power_MW_EE"] - df["PRC_Total_estimated_power_MW"]
    df["Power_EE_vs_SF_Diff"] = df["PRC_turbine_Matched_Turbine_power_MW_EE"] - df["PRC_turbine_Matched_Turbine_power_MW_SF"]
    df["Devaiation in steam flow (Simulated-actual)"] = df["PRC_turbine_Calculated_Steam_flow_TPH"] - df["PRC_turbine_steam_flow"]
    df["Devaiation in extraction (Simulated-actual)"] = df["PRC_turbine_Optimized_Extraction_flow_TPH"] - df["PRC_turbine_Extraction_flow"]
    df["Specific_steam_consumption_MT_MW_updated"] = df["PRC_turbine_Calculated_Steam_flow_TPH"] / df["PRC_Total_estimated_power_MW"]
    return df


# ---------------------------------------------------------------------------
# Constraint-limiting mask helper (CGC/PRC/ERC turbine RPM vs steam flow)
# ---------------------------------------------------------------------------

def _apply_rpm_constraint_limit(
    row_df: pd.DataFrame,
    constraints_df: pd.DataFrame,
    steam_flow_col: str,
    rpm_col: str,
) -> pd.DataFrame:
    steam_limit = constraints_df.loc[constraints_df["Parameter"] == steam_flow_col, "user input value"].values[0]
    rpm_limit = constraints_df.loc[constraints_df["Parameter"] == rpm_col, "user input value"].values[0]
    rpm_max = constraints_df.loc[constraints_df["Parameter"] == rpm_col, CONSTRAINTS_MAX_COL].values[0]
    mask = (row_df[steam_flow_col] < steam_limit) & (row_df[rpm_col] < rpm_limit)
    row_df.loc[mask, rpm_col] = rpm_max
    return row_df


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def whatif_analysis(
    df: pd.DataFrame,
    user_time: pd.Timestamp,
    user_input_df: pd.DataFrame,
    config: WhatIfConfig,
    model_dir: str,
    write_actual_vs_estimated_xlsx: bool = False,
    output_path: str | None = None,
) -> WhatIfResult:
    model_details_df = config.model_details_df
    constraints_df = config.constraints_df

    selected_row = df.loc[[user_time]].copy()
    selected_row.index.name = "Timestamp"
    selected_row_updated = selected_row.copy()

    def kalman(y_col: str) -> None:
        nonlocal selected_row_updated
        selected_row_updated = _predict_and_update_with_kalman(
            y_col, selected_row_updated, model_details_df, model_dir
        )

    def override(y_col: str) -> None:
        nonlocal selected_row_updated
        selected_row_updated = _update_parameter_from_user_input(
            y_col, user_input_df, selected_row_updated
        )

    # DMCTF feed — user override only
    override("DMCTF_feed")

    # Quench tower overhead temp — Kalman then override
    kalman("Quench_tower_overhead_temp")
    override("Quench_tower_overhead_temp")

    # CGC turbine RPM constraint-limit, then user override
    selected_row_updated = _apply_rpm_constraint_limit(
        selected_row_updated, constraints_df, "CGC_Turbine_HP_Steam_flow", "CGC_TURBINE_1_SPEED_(RPM)"
    )
    override("CGC_TURBINE_1_SPEED_(RPM)")

    kalman("CGC_STAGE_1_SUCTION_PRESSURE")
    override("CGC_STAGE_1_SUCTION_PRESSURE")

    # ---- COT calculation chain (actual then scenario) ----
    selected_row = _cot_calculation(selected_row)

    delta_cgc_suction_pressure_old = 0
    selected_row["Corrected_COP_Furnace"] = selected_row["Coil_Weighted_Avg_COP"] + delta_cgc_suction_pressure_old
    selected_row["Furnace_Effluent_C2H6"] = (
        (selected_row["DMCTF_feed"] / 1000) * (selected_row["Furnace_Normalised_Feed_C2H6_Wt"] / 100)
        * (1 - selected_row["Furnace_conversion"])
    )
    selected_row["Furnace_Effluent_C2H6_wt%"] = (
        selected_row["Furnace_Effluent_C2H6"] / (selected_row["DMCTF_feed"] / 1000)
    ) * 100
    selected_row["Coil_Avg_COT_actual"] = (
        (
            0.937913371 * (selected_row["Coil_CIP_Corrected_atma"] - 0.3)
            - 2.413045433 * (selected_row["Corrected_COP_Furnace"] / 101.325 + 1 - 0.2)
            + 2.774285758 * selected_row["Coil_Avg_SHC_Ratio"]
            + 0.002253435 * selected_row["Plant_average_feed_rate_Coil"]
            - 0.463411867 * selected_row["Furnace_Normalised_Feed_C3H8_Wt"]
            + 0.674941411 * selected_row["Furnace_Normalised_Feed_C2H6_Wt"]
            + 337.8851416 - selected_row["Furnace_Effluent_C2H6_wt%"]
        ) / 0.451606991
    )

    selected_row_updated = _cot_calculation(selected_row_updated)

    delta_cgc_suction_pressure = (
        selected_row_updated["CGC_STAGE_1_SUCTION_PRESSURE"] - selected_row["CGC_STAGE_1_SUCTION_PRESSURE"]
    )
    selected_row_updated["Corrected_COP_Furnace"] = (
        selected_row_updated["Coil_Weighted_Avg_COP"] + delta_cgc_suction_pressure
    )

    if (selected_row_updated["DMCTF_feed"].iloc[0] / 1000) - selected_row_updated["Fresh_ethane_feed"].iloc[0] > 70:
        selected_row_updated["Fresh_ethane_feed"] = (selected_row_updated["DMCTF_feed"] / 1000) - 70

    selected_row_updated["Furnace_conversion"] = (
        (selected_row_updated["DMCTF_feed"] / 1000) * (selected_row_updated["Furnace_Normalised_Feed_C2H6_Wt"] / 100)
        - (selected_row_updated["DMCTF_feed"] / 1000 - selected_row_updated["Fresh_ethane_feed"])
    ) / ((selected_row_updated["DMCTF_feed"] / 1000) * selected_row_updated["Furnace_Normalised_Feed_C2H6_Wt"] / 100)

    selected_row_updated["Furnace_Effluent_C2H6"] = (
        (selected_row_updated["DMCTF_feed"] / 1000) * (selected_row_updated["Furnace_Normalised_Feed_C2H6_Wt"] / 100)
        * (1 - selected_row_updated["Furnace_conversion"])
    )
    selected_row_updated["Furnace_Effluent_C2H6_wt%"] = (
        selected_row_updated["Furnace_Effluent_C2H6"] / (selected_row_updated["DMCTF_feed"] / 1000)
    ) * 100
    selected_row_updated["Coil_Avg_COT"] = (
        (
            0.937913371 * (selected_row_updated["Coil_CIP_Corrected_atma"] - 0.3)
            - 2.413045433 * (selected_row_updated["Corrected_COP_Furnace"] / 101.325 + 1 - 0.2)
            + 2.774285758 * selected_row_updated["Coil_Avg_SHC_Ratio"]
            + 0.002253435 * selected_row_updated["Plant_average_feed_rate_Coil"]
            - 0.463411867 * selected_row_updated["Furnace_Normalised_Feed_C3H8_Wt"]
            + 0.674941411 * selected_row_updated["Furnace_Normalised_Feed_C2H6_Wt"]
            + 337.8851416 - selected_row_updated["Furnace_Effluent_C2H6_wt%"]
        ) / 0.451606991
    )
    delta_cot = selected_row_updated["Coil_Avg_COT"] - selected_row["Coil_Avg_COT_actual"]
    selected_row_updated["Coil_Avg_COT"] = selected_row["Coil_Avg_COT"] + delta_cot

    # ---- CGC 5th stage discharge pressure + hard constraint gate ----
    kalman("CGC_5TH_STG_DISCH_PRES")
    override("CGC_5TH_STG_DISCH_PRES")

    param_name = "CGC_5TH_STG_DISCH_PRES"
    constraint_hit = False
    constraint_message = None
    mask = constraints_df["Parameter"] == param_name
    if mask.any():
        limit = constraints_df.loc[mask, "user input value"].values[0]
        if selected_row_updated[param_name].values[0] > limit:
            selected_row_updated[param_name] = "constraints hits: Reduce the DMCTF"
            constraint_hit = True
            constraint_message = "constraints hits: Reduce the DMCTF"

    if constraint_hit:
        result = _build_result(selected_row, selected_row_updated, user_time, constraint_hit, constraint_message)
        if write_actual_vs_estimated_xlsx and output_path:
            _write_actual_vs_estimated(selected_row, selected_row_updated, output_path)
        return result

    # ---- CGC power / steam flow ----
    kalman("CGC_Power_KW")
    kalman("CGC_Turbine_HP_Steam_flow")

    # ---- PRC section ----
    selected_row_updated = _apply_rpm_constraint_limit(
        selected_row_updated, constraints_df, "PRC_turbine_steam_flow", "PRC_turbine_RPM"
    )
    override("PRC_turbine_RPM")

    kalman("PRC_1ST_STAGE_Suction_FLOW")
    kalman("PRC_1ST_STAGE_Suction_PRESSURE")
    override("PRC_1ST_STAGE_Suction_PRESSURE")
    kalman("PRC_2nd_stage_drum_Overhead_Flow")

    selected_row_updated = _prc_section_power(selected_row_updated)
    selected_row_updated = _prc_turbine_extraction_steam_flow_prediction(selected_row_updated)

    # ---- ERC section ----
    selected_row_updated = _apply_rpm_constraint_limit(
        selected_row_updated, constraints_df, "ERC_turbine_steam_flow", "ERC_turbine_Speed"
    )
    override("ERC_turbine_Speed")

    kalman("ERC_2nd_stage_drum_Overhead_Flow")
    kalman("ERC_turbine_steam_flow")
    kalman("ERC_power")
    kalman("ERC_1ST_STAGE_Suction_FLOW")
    kalman("ERC_1ST_STAGE_Suction_PRESSURE")
    override("ERC_1ST_STAGE_Suction_PRESSURE")

    selected_row_updated["Total_Power_(KW)"] = (
        selected_row_updated["CGC_Power_KW"]
        + selected_row_updated["PRC_Total_estimated_power_MW"] * 1000
        + selected_row_updated["ERC_power"]
    )
    selected_row_updated["Total_required_steam_flow_(TPH)"] = (
        selected_row_updated["CGC_Turbine_HP_Steam_flow"]
        + selected_row_updated["PRC_turbine_Calculated_Steam_flow_TPH"]
        + selected_row_updated["ERC_turbine_steam_flow"]
    )

    kalman("TOTAL_ETHYLENE_LOSS_to_fuel")
    kalman("Ethylene_product_flow")

    result = _build_result(selected_row, selected_row_updated, user_time, constraint_hit=False, constraint_message=None)
    if write_actual_vs_estimated_xlsx and output_path:
        _write_actual_vs_estimated(selected_row, selected_row_updated, output_path)
    return result


def _build_result(
    actual_row: pd.DataFrame,
    estimated_row: pd.DataFrame,
    user_time: pd.Timestamp,
    constraint_hit: bool,
    constraint_message: str | None,
) -> WhatIfResult:
    actual = json.loads(actual_row.iloc[[0]].to_json(orient="records"))[0]
    estimated = json.loads(estimated_row.iloc[[0]].to_json(orient="records"))[0]
    actual["Timestamp"] = str(user_time)
    estimated["Timestamp"] = str(user_time)
    return WhatIfResult(
        actual=actual,
        estimated=estimated,
        constraint_hit=constraint_hit,
        constraint_message=constraint_message,
    )


def _write_actual_vs_estimated(actual_row: pd.DataFrame, estimated_row: pd.DataFrame, output_path: str) -> None:
    combined = pd.concat([actual_row, estimated_row], axis=0)
    combined.index = ["actual", "estimated"]
    combined.to_excel(output_path, engine="openpyxl")
