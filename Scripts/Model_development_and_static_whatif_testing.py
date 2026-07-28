# -*- coding: utf-8 -*-
"""
Model_development_and_static_whatif_testing.py
=================================================
Regenerated from Model_development_and_static_whatif_testing_updated.py for
this repo's single-plant (YANPET_OLF1) scope: trains one Kalman filter per
"Data model" row in Config_file.xlsx's "Model details" sheet (a generic,
config-driven loop -- no hardcoded parameter list), computes the furnace
weighted-average COT feature block, then hands off any "First principle"
predicted parameters to this plant's physics plug-in
(src/whatif/plants/yanpet_olf1_formulas.py) via its BULK_SIMULATION dict.

Differences from the _updated reference script this was regenerated from:
  - No PLANT_NAME / multi-plant folder resolution -- flat Data/, Results/,
    Results/Model/ layout (this repo's existing single-plant convention).
  - Reads Config_file.xlsx (this repo's canonical name), not
    Config_file_updated.xlsx.
  - The plant physics plug-in is imported directly as a Python package
    (src.whatif.plants.yanpet_olf1_formulas) instead of the reference's
    dynamic importlib multi-plant file search.
  - The ~1050 commented-out lines of superseded hardcoded what-if/LBT logic
    at the end of the reference script are removed entirely (not kept
    commented) -- that physics now lives in the plug-in; LBT/benchmark
    matching is out of scope for this rewrite.

Invoked as a subprocess by backend/app/services/what_if_service.py
(train_models()), with cwd=Scripts/ and MPLBACKEND=Agg set so plt.savefig
calls never try to open a GUI window.
"""
import os
import sys

# Run with cwd=Scripts/ (see backend/app/services/what_if_service.py), but
# the physics plug-in lives under the repo's src/ package -- put the repo
# root on sys.path so `from src.whatif.plants import ...` resolves regardless
# of the process's working directory.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score, mean_absolute_percentage_error
from sklearn.preprocessing import StandardScaler
import pickle
from nfoursid.nfoursid import NFourSID
from nfoursid.kalman import Kalman
import joblib

from src.whatif.plants import yanpet_olf1_formulas as _plant_formulas

# ---------------------------------------------------------------------
# Paths (flat single-plant layout, matches this repo's existing convention)
# ---------------------------------------------------------------------
file_path = "..\\Data"
RESULTS_DIR = "..\\Results"
RESULTS_MODEL_DIR = os.path.join(RESULTS_DIR, "Model")
os.makedirs(RESULTS_MODEL_DIR, exist_ok=True)

#%% data loading
_dmc_workbook_path = os.path.join(file_path, "DMC_Screen_tags_data.xlsx")
_dmc_sheet_names = pd.ExcelFile(_dmc_workbook_path).sheet_names
HAS_PI_DATA = "PI data" in _dmc_sheet_names
HAS_FURNACE_DATA = "Furnace data" in _dmc_sheet_names
print(f"[whatif_train] DMC_Screen_tags_data.xlsx sheets found: {_dmc_sheet_names} "
      f"(PI data={HAS_PI_DATA}, Furnace data={HAS_FURNACE_DATA})")
if not HAS_PI_DATA and not HAS_FURNACE_DATA:
    raise ValueError(
        "DMC_Screen_tags_data.xlsx must contain at least one of the sheets "
        "'PI data' or 'Furnace data'. Found: " + str(_dmc_sheet_names)
    )

df = None
if HAS_PI_DATA:
    df = pd.read_excel(_dmc_workbook_path, sheet_name="PI data")
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)
    df.set_index("Timestamp", inplace=True)

    df["CGC_Power_KW"] = (
        df["CGC_Stage_1_power"] + df["CGC_Stage_2_power"] + df["CGC_Stage_3_power"]
        + df["CGC_Stage_4_power"] + df["CGC_Stage_5_power"]
    )

    df.dropna(inplace=True)
    df = df.apply(pd.to_numeric, errors='coerce')

df_stats = df.describe(include='all') if df is not None else None

#%% Furnace average COT calculation
if HAS_FURNACE_DATA:
    df_furnace = pd.read_excel(_dmc_workbook_path, sheet_name="Furnace data")

    df_furnace.columns = df_furnace.iloc[0]
    df_furnace = df_furnace[1:].reset_index(drop=True)
    df_furnace.columns = df_furnace.columns.str.strip()

    if "Timestamp" in df_furnace.columns:
        df_furnace.set_index("Timestamp", inplace=True)

    df_furnace = df_furnace.apply(pd.to_numeric, errors='coerce')

    metrics_config = [
        ('Global_WA_COT', 'Furnace_Coil_Outlet_Temperature_Coil', 'Furnace_Feed_Rate_Coil'),
        ('Global_WA_CIP', 'Coil', 'Furnace_Feed_Rate_Coil', '_CIP_Corrected_atma'),
        ('Global_WA_SHC', 'Furnace_Coil', 'Furnace_Feed_Rate_Coil', '_SHC_Ratio'),
        ('Global_WA_Feed_CV', 'Furnace_Feed_Coil', 'Furnace_Feed_Rate_Coil', '_CV_Opening'),
        ('Global_WA_Steam_CV', 'Furnace_Dilution_Steam_Coil', 'Furnace_Feed_Rate_Coil', '_CV_Opening'),
        ('Global_WA_Mixed_Feed_Temp', 'Coil', 'Furnace_Feed_Rate_Coil', '_Mixed_Feed_Inlet_Temperature'),
    ]

    total_valid_feed_sum = pd.Series(0, index=df_furnace.index, dtype=float)
    weighted_sums = {name: pd.Series(0, index=df_furnace.index, dtype=float) for name, *_ in metrics_config}

    for furnace in range(1, 13):
        status_col = f'F{furnace}_online_status'
        if status_col in df_furnace.columns:
            status_mask = (df_furnace[status_col] == 1)
        else:
            status_mask = pd.Series(True, index=df_furnace.index)

        for coil in range(1, 5):
            feed_col = f'F{furnace}_Furnace_Feed_Rate_Coil{coil}'
            if feed_col not in df_furnace.columns:
                continue

            feed_series = df_furnace[feed_col]
            feed_valid = feed_series.fillna(0) > 0
            base_mask = status_mask & feed_valid
            current_feed = feed_series.fillna(0).where(base_mask, 0)

            for config in metrics_config:
                metric_name = config[0]
                if len(config) == 3:
                    val_col = f'F{furnace}_{config[1]}{coil}'
                else:
                    val_col = f'F{furnace}_{config[1]}{coil}{config[3]}'

                if val_col not in df_furnace.columns:
                    continue

                val_series = df_furnace[val_col]
                valid_data_mask = base_mask & val_series.notna()
                valid_feed = current_feed.where(valid_data_mask, 0)
                valid_value = val_series.where(valid_data_mask, 0)

                weighted_sums[metric_name] += (valid_value * valid_feed)
                if f"{metric_name}_feed" not in weighted_sums:
                    weighted_sums[f"{metric_name}_feed"] = pd.Series(0, index=df_furnace.index, dtype=float)
                weighted_sums[f"{metric_name}_feed"] += valid_feed

    for metric_name in [c[0] for c in metrics_config]:
        result_col = f"{metric_name}_AllCoils"
        feed_col = f"{metric_name}_feed"
        denominator = weighted_sums[feed_col]
        numerator = weighted_sums[metric_name]
        df_furnace[result_col] = np.where(denominator > 0, numerator / denominator, np.nan)

    print("Calculation complete with NaN handling.")
    print(df_furnace.filter(like="Global_WA").head())

    global_weighted_sum_cop = pd.Series(0, index=df_furnace.index, dtype=float)
    global_valid_feed_cop = pd.Series(0, index=df_furnace.index, dtype=float)

    for furnace in range(1, 13):
        feed_1 = f'F{furnace}_Furnace_Feed_Rate_Coil1'
        feed_2 = f'F{furnace}_Furnace_Feed_Rate_Coil2'
        feed_3 = f'F{furnace}_Furnace_Feed_Rate_Coil3'
        feed_4 = f'F{furnace}_Furnace_Feed_Rate_Coil4'
        cop_tlea = f'F{furnace}_Corrected_COP_Furnace_TLEA'
        cop_tleb = f'F{furnace}_Corrected_COP_Furnace_TLEB'
        status_col = f'F{furnace}_online_status'
        required_cols = [feed_1, feed_2, feed_3, feed_4, cop_tlea, cop_tleb, status_col]

        if all(col in df_furnace.columns for col in required_cols):
            f1 = df_furnace[feed_1].fillna(0)
            f2 = df_furnace[feed_2].fillna(0)
            f3 = df_furnace[feed_3].fillna(0)
            f4 = df_furnace[feed_4].fillna(0)
            cop_a = df_furnace[cop_tlea]
            cop_b = df_furnace[cop_tleb]
            status = df_furnace[status_col]
            base_mask = (status == 1)

            feed_tlea = f1 + f2
            mask_tlea = base_mask & (feed_tlea > 0) & cop_a.notna()
            feed_tleb = f3 + f4
            mask_tleb = base_mask & (feed_tleb > 0) & cop_b.notna()

            term_a = (cop_a * feed_tlea).where(mask_tlea, 0)
            term_b = (cop_b * feed_tleb).where(mask_tleb, 0)
            global_weighted_sum_cop += term_a + term_b
            global_valid_feed_cop += feed_tlea.where(mask_tlea, 0) + feed_tleb.where(mask_tleb, 0)

    df_furnace['Global_Weighted_Avg_COP_AllCoils'] = np.where(
        global_valid_feed_cop > 0, global_weighted_sum_cop / global_valid_feed_cop, np.nan
    )

    col_rename = {
        'Global_WA_COT_AllCoils': 'Coil_Avg_COT',
        'Global_WA_CIP_AllCoils': 'Coil_Avg_CIP',
        'Global_WA_SHC_AllCoils': 'Coil_Avg_SHC_Ratio',
        'Global_Weighted_Avg_COP_AllCoils': 'Coil_Weighted_Avg_COP',
        'Global_WA_Feed_CV_AllCoils': 'Coil_Weighted_Avg_Feed_CV_opening',
        'Global_WA_Steam_CV_AllCoils': 'Coil_Weighted_Avg_Steam_CV_opening',
        'Global_WA_Mixed_Feed_Temp_AllCoils': 'Coil_Weighted_Avg_Coil_Mixed_Feed_Inlet_Temperature',
    }
    df_furnace.rename(columns=col_rename, inplace=True, errors='ignore')

    df_furnace["Furnace_Sum_of_Feed_Components"] = (
        df_furnace["Furnace_Ethane_Feed_Preheater_Ethane_Feed_CH4"]
        + df_furnace["Furnace_Ethane_Feed_Preheater_Ethane_Feed_C2H6"]
        + df_furnace["Furnace_Ethane_Feed_Preheater_Ethane_Feed_C3H8"]
    )
    df_furnace['Furnace_Normalised_Feed_CH4'] = (
        df_furnace['Furnace_Ethane_Feed_Preheater_Ethane_Feed_CH4'] * 100 / df_furnace["Furnace_Sum_of_Feed_Components"]
    )
    df_furnace["Furnace_Normalised_Feed_C2H6"] = (
        df_furnace['Furnace_Ethane_Feed_Preheater_Ethane_Feed_C2H6'] * 100 / df_furnace["Furnace_Sum_of_Feed_Components"]
    )
    df_furnace["Furnace_Normalised_Feed_C3H8"] = (
        df_furnace['Furnace_Ethane_Feed_Preheater_Ethane_Feed_C3H8'] * 100 / df_furnace["Furnace_Sum_of_Feed_Components"]
    )

    df_furnace['Furnace_Normalised_Feed_CH4_Wt'] = (
        df_furnace['Furnace_Normalised_Feed_CH4'] * 16 * 100
        / (df_furnace['Furnace_Normalised_Feed_CH4'] * 16 + df_furnace["Furnace_Normalised_Feed_C2H6"] * 30 + df_furnace["Furnace_Normalised_Feed_C3H8"] * 44)
    )
    df_furnace['Furnace_Normalised_Feed_C2H6_Wt'] = (
        df_furnace['Furnace_Normalised_Feed_C2H6'] * 30 * 100
        / (df_furnace['Furnace_Normalised_Feed_CH4'] * 16 + df_furnace["Furnace_Normalised_Feed_C2H6"] * 30 + df_furnace["Furnace_Normalised_Feed_C3H8"] * 44)
    )
    df_furnace['Furnace_Normalised_Feed_C3H8_Wt'] = (
        df_furnace['Furnace_Normalised_Feed_C3H8'] * 44 * 100
        / (df_furnace['Furnace_Normalised_Feed_CH4'] * 16 + df_furnace["Furnace_Normalised_Feed_C2H6"] * 30 + df_furnace["Furnace_Normalised_Feed_C3H8"] * 44)
    )
    df_furnace["Furnace_Feed_Average_Molecular_Wt"] = (
        df_furnace['Furnace_Normalised_Feed_CH4'] / 100 * 16
        + df_furnace["Furnace_Normalised_Feed_C2H6"] / 100 * 30
        + df_furnace["Furnace_Normalised_Feed_C3H8"] / 100 * 44
    )

    df_furnace['Furnace_conversion'] = (
        (df_furnace['DMCTF_feed'] / 1000) * (df_furnace['Furnace_Normalised_Feed_C2H6_Wt'] / 100)
        - (df_furnace['DMCTF_feed'] / 1000 - df_furnace['Fresh ethane feed'])
    ) / ((df_furnace['DMCTF_feed'] / 1000) * df_furnace['Furnace_Normalised_Feed_C2H6_Wt'] / 100)

    df_furnace['Furnace_Effluent_C2H6'] = (
        (df_furnace['DMCTF_feed'] / 1000) * (df_furnace['Furnace_Normalised_Feed_C2H6_Wt'] / 100) * (1 - df_furnace['Furnace_conversion'])
    )
    df_furnace['Furnace_Effluent_C2H6_wt%'] = (df_furnace['Furnace_Effluent_C2H6'] / (df_furnace['DMCTF_feed'] / 1000)) * 100
    df_furnace['Plant_average_feed_rate_Coil'] = df_furnace["DMCTF_feed"] / (df_furnace["Number_Of_Furnaces_Online"] * 4)

    df_furnace['Coil_CIP_Calculated'] = (
        -131.3081
        + (0.0755 * df_furnace['Plant_average_feed_rate_Coil'])
        + (0.1463 * df_furnace['Ethane_Feed_Preheater_Ethane_Feed_Outlet_Pressure'])
        + (0.6819 * df_furnace['Furnace_Ethane_Feed_Preheater_Ethane_Feed_Outlet_Temperature'])
        + (0.4853 * df_furnace['Coil_Weighted_Avg_Feed_CV_opening'])
        + (0.8766 * df_furnace['Coil_Weighted_Avg_Steam_CV_opening'])
    )

    df_furnace['Coil_Steam_Flow'] = (df_furnace['Coil_Avg_SHC_Ratio'] * df_furnace['Plant_average_feed_rate_Coil'])
    df_furnace['Coil_Mixed_Feed_flow'] = df_furnace['Coil_Steam_Flow'] + df_furnace['Plant_average_feed_rate_Coil']
    df_furnace['Coil_Mixed_Feed_Cp'] = (
        (df_furnace['Coil_Steam_Flow'] * 2.067) + (df_furnace['Plant_average_feed_rate_Coil'] * 1.909)
    ) / (df_furnace['Coil_Steam_Flow'] + df_furnace['Plant_average_feed_rate_Coil'])
    df_furnace['Coil_Mixed_Feed_Mol_wt'] = (
        df_furnace['Coil_Mixed_Feed_flow']
        / ((df_furnace['Plant_average_feed_rate_Coil'] / df_furnace["Furnace_Feed_Average_Molecular_Wt"]) + (df_furnace['Coil_Steam_Flow'] / 18.0))
    )
    df_furnace['Coil_Volumetric_Flow'] = (
        df_furnace['Coil_Mixed_Feed_flow']
    ) / (
        ((df_furnace['Coil_CIP_Calculated'] + 101.325) * 0.00982963 * df_furnace['Coil_Mixed_Feed_Mol_wt'])
        / (0.08206 * (df_furnace['Coil_Weighted_Avg_Coil_Mixed_Feed_Inlet_Temperature'] + 273.15))
    )
    df_furnace['Coil_CIP_Corrected_atma'] = np.where(
        (df_furnace['Coil_CIP_Calculated'] / 101.325 + 1) < 5,
        (df_furnace['Coil_CIP_Calculated'] / 101.325 + 1) - (df_furnace['Coil_Volumetric_Flow'] * 144 / 1309.83) * 0.00986923,
        (df_furnace['Coil_CIP_Calculated'] / 101.325 + 1) - (df_furnace['Coil_Volumetric_Flow'] * 131 / 1209.52) * 0.00986923,
    )

    selected_col = [
        'Coil_Avg_COT', 'Ethane_Feed_Preheater_Ethane_Feed_Outlet_Pressure',
        'Furnace_Ethane_Feed_Preheater_Ethane_Feed_Outlet_Temperature', 'Coil_Weighted_Avg_Feed_CV_opening',
        'Coil_Weighted_Avg_Steam_CV_opening', 'Coil_Avg_SHC_Ratio', 'Coil_Weighted_Avg_COP',
        'Coil_Weighted_Avg_Coil_Mixed_Feed_Inlet_Temperature', "Furnace_Feed_Average_Molecular_Wt",
        'Coil_CIP_Calculated', 'Coil_Steam_Flow', 'Coil_Mixed_Feed_flow', 'Coil_Mixed_Feed_Cp',
        'Coil_Mixed_Feed_Mol_wt', 'Coil_Volumetric_Flow', 'Coil_CIP_Corrected_atma',
        'Furnace_Normalised_Feed_C2H6_Wt', 'Furnace_Normalised_Feed_C3H8_Wt', "Number_Of_Furnaces_Online",
        'Furnace_conversion', 'Furnace_Effluent_C2H6', 'Furnace_Effluent_C2H6_wt%',
    ]
    df_furnace_truncate = df_furnace[selected_col]

if HAS_PI_DATA and HAS_FURNACE_DATA:
    df = df.merge(df_furnace_truncate, how="inner", left_index=True, right_index=True)
elif HAS_FURNACE_DATA and not HAS_PI_DATA:
    print("[whatif_train] 'PI data' sheet not supplied; using 'Furnace data' alone as the training table.")
    df = df_furnace_truncate.copy()
    df_stats = df.describe(include='all')

#%% Config file loading
config_df_model_details = pd.read_excel(os.path.join(file_path, "Config_file.xlsx"), sheet_name='Model details')

#%% Generic Kalman-filter training loop
_INPUT_PARAM_COLS = [c for c in config_df_model_details.columns
                     if str(c).strip().lower().startswith("input parameter")]

_MODEL_TYPE_COL = next(
    (c for c in config_df_model_details.columns
     if str(c).strip().lower() in ("model", "model type", "model_type")
     or ("model" in str(c).strip().lower() and "type" in str(c).strip().lower())),
    None
)


def _model_type_for(y_col: str) -> str:
    if _MODEL_TYPE_COL is None:
        return ""
    rows = config_df_model_details.loc[
        config_df_model_details["Predicted parameter"] == y_col, _MODEL_TYPE_COL
    ]
    if rows.empty or pd.isna(rows.iloc[0]):
        return ""
    return str(rows.iloc[0]).strip().lower()


def _is_data_model(y_col: str) -> bool:
    mtype = _model_type_for(y_col)
    return mtype == "" or "data" in mtype


predicted_parameters = (
    config_df_model_details["Predicted parameter"].dropna().astype(str).str.strip()
)
predicted_parameters = [p for p in predicted_parameters.unique() if p]

print(f"[whatif_train] {len(predicted_parameters)} predicted parameter(s) found: {predicted_parameters}")

trained_parameters = []
skipped_parameters = []
simulation_parameters = []
accuracy_records = []

for y_col in predicted_parameters:
    if not _is_data_model(y_col):
        mtype = _model_type_for(y_col) or "(unspecified)"
        print(f"[whatif_train] '{y_col}' is a '{mtype}' model, not a Data model -- skipping Kalman training.")
        simulation_parameters.append(y_col)
        accuracy_records.append({
            "Predicted parameter": y_col, "Status": "Simulation/first-principle (not trained here)",
            "Model type": mtype, "Input parameters": "", "Train rows": np.nan, "Test rows": np.nan,
            "RMSE": np.nan, "MAE": np.nan, "MAPE_%": np.nan, "R2": np.nan,
        })
        continue

    print(f"\n{'='*70}\n[whatif_train] Training model for predicted parameter: '{y_col}'\n{'='*70}")

    row = config_df_model_details[config_df_model_details["Predicted parameter"] == y_col]
    u_cols = row[_INPUT_PARAM_COLS].dropna(axis=1).values.ravel().tolist()
    u_cols = [str(c).strip() for c in u_cols if str(c).strip()]

    if not u_cols:
        print(f"[whatif_train] SKIPPING '{y_col}' -- no input parameters listed for it in Model details.")
        skipped_parameters.append(y_col)
        accuracy_records.append({
            "Predicted parameter": y_col, "Status": "Skipped (no input parameters listed)",
            "Model type": "Data model", "Input parameters": "", "Train rows": np.nan, "Test rows": np.nan,
            "RMSE": np.nan, "MAE": np.nan, "MAPE_%": np.nan, "R2": np.nan,
        })
        continue

    missing_cols = [c for c in ([y_col] + u_cols) if c not in df.columns]
    if missing_cols:
        print(f"[whatif_train] SKIPPING '{y_col}' -- missing column(s) in the training data: {missing_cols}.")
        skipped_parameters.append(y_col)
        accuracy_records.append({
            "Predicted parameter": y_col, "Status": f"Skipped (missing column(s): {missing_cols})",
            "Model type": "Data model", "Input parameters": ", ".join(u_cols), "Train rows": np.nan,
            "Test rows": np.nan, "RMSE": np.nan, "MAE": np.nan, "MAPE_%": np.nan, "R2": np.nan,
        })
        continue

    X = df[u_cols].values
    y = df[y_col].values

    X_train, X_test, y_train, y_test = train_test_split(df[u_cols], df[y_col], test_size=0.2, shuffle=True)

    scaler_X = StandardScaler()
    scaler_y = StandardScaler()

    X_scaled_train = scaler_X.fit_transform(X_train)
    y_scaled_train = scaler_y.fit_transform(y_train.values.reshape(-1, 1))
    X_scaled_test = scaler_X.transform(X_test)
    y_scaled_test = scaler_y.transform(y_test.values.reshape(-1, 1))

    X_scaled_train = pd.DataFrame(X_scaled_train, columns=u_cols, index=X_train.index)
    X_scaled_test = pd.DataFrame(X_scaled_test, columns=u_cols, index=X_test.index)
    y_scaled_train = pd.DataFrame(y_scaled_train, columns=[y_col], index=y_train.index)
    y_scaled_test = pd.DataFrame(y_scaled_test, columns=[y_col], index=y_test.index)

    train_data = pd.concat([X_scaled_train, y_scaled_train], axis=1)
    test_data = pd.concat([X_scaled_test, y_scaled_test], axis=1)

    common_index = train_data.index.intersection(test_data.index)
    print(f"Number of common rows based on timestamp index: {len(common_index)}")

    X_scaled_train = X_scaled_train.to_numpy()
    X_scaled_test = X_scaled_test.to_numpy()
    y_scaled_train = y_scaled_train.to_numpy()
    y_scaled_test = y_scaled_test.to_numpy()

    try:
        nfoursid_model = NFourSID(
            train_data, output_columns=[y_col], input_columns=u_cols, num_block_rows=10
        )
        nfoursid_model.subspace_identification()
        state_space, _ = nfoursid_model.system_identification(rank=2)
    except Exception as fit_err:
        print(f"[whatif_train] SKIPPING '{y_col}' -- system identification failed: {fit_err}")
        skipped_parameters.append(y_col)
        accuracy_records.append({
            "Predicted parameter": y_col, "Status": f"Skipped (system identification failed: {fit_err})",
            "Model type": "Data model", "Input parameters": ", ".join(u_cols),
            "Train rows": len(X_train), "Test rows": len(X_test),
            "RMSE": np.nan, "MAE": np.nan, "MAPE_%": np.nan, "R2": np.nan,
        })
        continue

    D_matrix = state_space.d
    D_matrix = pd.DataFrame(D_matrix, columns=u_cols, index=[y_col]).round(2)
    B_matrix = state_space.b
    B_matrix = pd.DataFrame(B_matrix, columns=u_cols, index=[f'State_{i}' for i in range(B_matrix.shape[0])]).round(4)

    input_influence_B = np.linalg.norm(B_matrix, axis=0)
    input_importance_B = pd.Series(input_influence_B, index=u_cols).sort_values(ascending=False)
    print("Input Importance (via B matrix):")
    print(input_importance_B)

    total_importance = pd.Series(
        input_influence_B + np.abs(D_matrix.to_numpy()).flatten(), index=u_cols
    ).sort_values(ascending=False)
    print("Overall Variable Importance:")
    print(total_importance)

    fig_imp = plt.figure()
    total_importance.plot(kind='barh', title=f'Variable_Importance_for {y_col}')
    plt.xlabel('Composite Importance Score (B + D)')
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_MODEL_DIR, f'variable_importance_{y_col}.png'))
    plt.close(fig_imp)

    kalman = Kalman(state_space=state_space, noise_covariance=np.eye(3))
    for i in range(len(X_scaled_test)):
        u_step = X_scaled_test[i].reshape(-1, 1)
        kalman.step(y=None, u=u_step)

    results_test = kalman.to_dataframe()
    y_pred_scaled = results_test[('$y_0$', 'filtered', 'output')].values
    y_pred = scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1)).ravel()
    y_true = y_test.values.ravel()

    fig_pred = plt.figure(figsize=(12, 5))
    plt.plot(y_true, label='Measured', alpha=0.7)
    plt.plot(y_pred, label='Predicted (Kalman)', linestyle='--')
    plt.legend()
    plt.xlabel('Time Step')
    plt.ylabel(f'{y_col}')
    plt.title(f'{y_col}_Prediction')
    plt.grid(True)
    plt.savefig(os.path.join(RESULTS_MODEL_DIR, f'prediction_plot_{y_col}.png'))
    plt.close(fig_pred)

    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    r2 = r2_score(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    try:
        mape = mean_absolute_percentage_error(y_true, y_pred) * 100
    except Exception:
        mape = np.nan
    print(f"RMSE: {rmse:.3f}")
    print(f"R²: {r2:.3f}")
    print(f"MAE: {mae:.3f}")
    if pd.notna(mape):
        print(f"MAPE: {mape:.2f}%")

    with open(os.path.join(RESULTS_MODEL_DIR, f'kalman_filter_model_{y_col}.pkl'), 'wb') as f:
        pickle.dump(kalman, f)
    joblib.dump(scaler_X, os.path.join(RESULTS_MODEL_DIR, f'scaler_X_{y_col}.pkl'))
    joblib.dump(scaler_y, os.path.join(RESULTS_MODEL_DIR, f'scaler_y_{y_col}.pkl'))

    trained_parameters.append(y_col)
    accuracy_records.append({
        "Predicted parameter": y_col,
        "Status": "Trained",
        "Model type": _model_type_for(y_col) or "Data model",
        "Input parameters": ", ".join(u_cols),
        "Train rows": len(X_scaled_train),
        "Test rows": len(X_scaled_test),
        "RMSE": round(float(rmse), 4),
        "MAE": round(float(mae), 4),
        "MAPE_%": round(float(mape), 2) if pd.notna(mape) else np.nan,
        "R2": round(float(r2), 4),
    })

#%% Bulk simulation / first-principle parameters (via this plant's plug-in)
_bulk_sim = getattr(_plant_formulas, "BULK_SIMULATION", {}) or {}


def _set_accuracy_status(y_col: str, status: str):
    for _rec in accuracy_records:
        if _rec["Predicted parameter"] == y_col:
            _rec["Status"] = status
            return


for y_col in simulation_parameters:
    sim_func = _bulk_sim.get(y_col)
    if sim_func is None:
        print(f"[whatif_train] '{y_col}' is a simulation/first-principle parameter but has no "
              f"BULK_SIMULATION entry in yanpet_olf1_formulas.py -- leaving it out of "
              f"Raw_data_plus_simulated_data.xlsx.")
        _set_accuracy_status(y_col, "Simulation (no BULK_SIMULATION function registered for it)")
        continue
    try:
        df[y_col] = sim_func(df.copy())
        print(f"[whatif_train] Computed '{y_col}' via its simulation/first-principle formula for all {len(df)} historian rows.")
        _set_accuracy_status(y_col, "Simulated (bulk first-principle formula)")
    except Exception as sim_err:
        print(f"[whatif_train] SKIPPING bulk simulation for '{y_col}' -- {sim_err}")
        _set_accuracy_status(y_col, f"Simulation failed: {sim_err}")

print(f"\n[whatif_train] Training complete: {len(trained_parameters)} Kalman model(s) trained "
      f"({trained_parameters}); {len(simulation_parameters)} left to the physics plug-in "
      f"({simulation_parameters}); {len(skipped_parameters)} skipped due to missing data ({skipped_parameters}).")

#%% Save per-model accuracy summary
accuracy_df = pd.DataFrame(accuracy_records, columns=[
    "Predicted parameter", "Status", "Model type", "Input parameters",
    "Train rows", "Test rows", "RMSE", "MAE", "MAPE_%", "R2",
])
accuracy_df.to_excel(os.path.join(RESULTS_MODEL_DIR, "Model_accuracy_summary.xlsx"), index=False)
accuracy_df.to_csv(os.path.join(RESULTS_MODEL_DIR, "Model_accuracy_summary.csv"), index=False)
print(f"\n[whatif_train] Saved accuracy summary for {len(accuracy_df)} predicted parameter(s) to "
      f"{os.path.join(RESULTS_MODEL_DIR, 'Model_accuracy_summary.xlsx')}")
print(accuracy_df.to_string(index=False))

# ---------------------------------------------------------------------
# Plant-wide totals (YANPET_OLF1's own CGC/PRC/ERC naming) -- guarded so a
# missing column just skips this summary instead of crashing the run.
# ---------------------------------------------------------------------
try:
    df["Total_Power_(KW)"] = df["CGC_Power_KW"] + df["PRC_Total_estimated_power_MW"] * 1000 + df["ERC_power"]
    df["Total_required_steam_flow_(TPH)"] = (
        df["CGC_Turbine_HP_Steam_flow"] + df["PRC_turbine_Calculated_Steam_flow_TPH"] + df["ERC_turbine_steam_flow"]
    )
except KeyError as _missing:
    print(f"[whatif_train] Skipping Total_Power_(KW) / Total_required_steam_flow_(TPH) summary columns "
          f"-- missing {_missing}.")

df.to_excel(os.path.join(RESULTS_DIR, 'Raw_data_plus_simulated_data.xlsx'))

df_corr = df.corr(method="pearson").round(2)


def color_columns(val):
    if val > 0.4:
        return 'background-color: green'
    elif val < -0.4:
        return 'background-color: red'
    return ''


with pd.ExcelWriter(os.path.join(RESULTS_DIR, 'correlation_with_color_conditioning.xlsx'), engine='openpyxl') as writer:
    df_corr.style.map(color_columns).to_excel(writer, index=True)
