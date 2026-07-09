# -*- coding: utf-8 -*-
"""
Created on Thu Apr  9 12:55:23 2026

@author: 30793167 : Sumit Kumar
"""
# Import libraries

import pandas as pd
import numpy as np
import random
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.svm import SVR
import os
from plotly.offline import plot
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, mean_absolute_percentage_error
import pickle
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from scipy.signal import cont2discrete
from nfoursid.nfoursid import NFourSID
from nfoursid.state_space import StateSpace
from nfoursid.kalman import Kalman
import joblib
from CoolProp.CoolProp import PropsSI
from scipy.optimize import minimize_scalar
import ipywidgets as widgets
from IPython.display import display
import plotly.graph_objects as go
import plotly.io as pio

file_path= "..\\Data"

def load_process_data() -> pd.DataFrame:
    """Load and preprocess DMC_Screen_tags_data.xlsx PI data sheet."""
    df = pd.read_excel(
        os.path.join("..\\Results", 'Raw_data_plus_simulated_data.xlsx'),
    )
    df.set_index('Timestamp', inplace=True)
    return df

df= load_process_data()

#%% what if preparation for YANPET OLF1
def whatif_analysis(df, user_time, user_input_df):
    config_df_model_details = pd.read_excel(file_path +"/" + "Config_file.xlsx", sheet_name= 'Model details')
    constraints_df = pd.read_excel(file_path + "/" + 'Config_file.xlsx',sheet_name= "Constraints")
    user_time = user_time
    row = df.loc[user_time]
    
    # user_input = input("Enter timestamp (YYYY-MM-DD HH:MM:SS):")
    user_input = user_time
    selected_row = df.loc[user_input]
    selected_row = pd.DataFrame(selected_row).T  # Convert Series to DataFrame
    selected_row.index.name = "Timestamp"

    selected_row_updated = selected_row.copy()

    def predict_and_update_with_kalman(
        y_col: str, 
        selected_row_updated: pd.DataFrame, 
        config_df_model_details: pd.DataFrame, 
        results_dir: str = "..\\Results\\Model"
    ) -> pd.DataFrame:
        """
        Generalizes the Kalman filter loading, scaling, prediction, and dataframe update process
        for any target column (y_col).
        
        Parameters:
        - y_col: The target parameter name (string).
        - selected_row_updated: The input DataFrame containing feature data.
        - config_df_model_details: DataFrame containing configuration mapping for features.
        - results_dir: Directory where models and scalers are stored.
        
        Returns:
        - selected_row_updated with the predicted value updated for y_col.
        """
        # 1. Extract feature columns dynamically
        u_cols = config_df_model_details[config_df_model_details["Predicted parameter"] == y_col]
        u_cols = u_cols.dropna(axis=1)
        u_cols = u_cols.iloc[:, 1:].values.ravel().tolist()

        # 2. Construct dynamic file paths
        model_path = os.path.join(results_dir, f'kalman_filter_model_{y_col}.pkl')
        scaler_x_path = os.path.join(results_dir, f'scaler_X_{y_col}.pkl')
        scaler_y_path = os.path.join(results_dir, f'scaler_y_{y_col}.pkl')

        # 3. Load the model and scalers dynamically
        with open(model_path, 'rb') as f:
            kalman_model = pickle.load(f)

        scaler_X = joblib.load(scaler_x_path)
        scaler_y = joblib.load(scaler_y_path)

        # 4. Prepare data and run the Kalman filter step
        feature_df = selected_row_updated[u_cols]
        scaled_test = scaler_X.transform(feature_df)
        kalman_model.step(y=None, u=scaled_test.reshape(-1, 1))

        # 5. Extract results and inverse transform
        results = kalman_model.to_dataframe()
        pred_scaled = results[('$y_0$', 'filtered', 'output')].iloc[-1]
        pred_unscaled = scaler_y.inverse_transform([[pred_scaled]]).ravel()

        # 6. Update the DataFrame dynamically using `loc`
        selected_row_updated.loc[:, y_col] = pred_unscaled[0]

        return selected_row_updated

    def update_parameter_from_user_input(
        y_col: str, 
        user_input_df: pd.DataFrame, 
        selected_row_updated: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Generalizes fetching user input for a specific parameter (y_col),
        handling type conversion/NaNs, and updating the selected_row_updated dataframe 
        if a valid user input exists.
        
        Parameters:
        - y_col: The target parameter name (string).
        - user_input_df: DataFrame containing user inputs with "Parameter" and "Value" columns.
        - selected_row_updated: DataFrame (or Series) containing the current row/values.
        
        Returns:
        - selected_row_updated with the parameter updated if valid user input is provided.
        """
        # 1. Fetch user input for the specific parameter dynamically
        matching_input = user_input_df.loc[user_input_df["Parameter"].str.strip() == y_col, 'Value']
        raw_input_val = matching_input.iloc[0] if not matching_input.empty else np.nan
        
        # 2. Convert to float and handle NaN / exceptions safely
        try:
            user_value = float(raw_input_val) if pd.notna(raw_input_val) else np.nan
        except (ValueError, TypeError):
            user_value = np.nan

        # 3. Safely extract the current/default value from selected_row_updated
        current_val_series = selected_row_updated.get(y_col, np.nan)
        current_value = current_val_series.iloc[0] if isinstance(current_val_series, pd.Series) and not current_val_series.empty else current_val_series

        # 4. Update with user input if valid, otherwise keep the current value
        final_value = user_value if not np.isnan(user_value) else current_value
        
        # Assign back safely using .loc if it's a DataFrame or dictionary-like assignment
        if isinstance(selected_row_updated, pd.DataFrame):
            selected_row_updated.loc[:, y_col] = final_value
        else:
            selected_row_updated[y_col] = final_value

        return selected_row_updated

    #User based DNCTF input updation
    y_col = "DMCTF_feed"
    selected_row_updated = update_parameter_from_user_input(
        y_col=y_col,
        user_input_df=user_input_df,
        selected_row_updated=selected_row_updated
    )

    # Quench section prediction updation
    y_col = "Quench_tower_overhead_temp"
    selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
    )

    y_col = "Quench_tower_overhead_temp"
    selected_row_updated = update_parameter_from_user_input(
        y_col=y_col,
        user_input_df=user_input_df,
        selected_row_updated=selected_row_updated
    )

    # CGC suction pressure prediction updation
    mask = (selected_row_updated['CGC_Turbine_HP_Steam_flow'] < constraints_df[constraints_df["Parameter"]=="CGC_Turbine_HP_Steam_flow"]["user input value"].values[0]) & (selected_row_updated['CGC_TURBINE_1_SPEED_(RPM)'] < constraints_df[constraints_df["Parameter"]=="CGC_TURBINE_1_SPEED_(RPM)"]["user input value"].values[0])
    selected_row_updated.loc[mask, 'CGC_TURBINE_1_SPEED_(RPM)'] = constraints_df[constraints_df["Parameter"]=="CGC_TURBINE_1_SPEED_(RPM)"]["Max vlaue"].values[0] 

    #KT1301 Turbine RPM user based input
    y_col = 'CGC_TURBINE_1_SPEED_(RPM)'
    selected_row_updated = update_parameter_from_user_input(
        y_col=y_col,
        user_input_df=user_input_df,
        selected_row_updated=selected_row_updated
    )

    y_col = "CGC_STAGE_1_SUCTION_PRESSURE"
    selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
    )

    # CGC Suction pressure user based value 
    y_col = "CGC_STAGE_1_SUCTION_PRESSURE"
    selected_row_updated = update_parameter_from_user_input(
        y_col=y_col,
        user_input_df=user_input_df,
        selected_row_updated=selected_row_updated
    )


    #Overall COT analysis
    def COT_calculation(df_furnace):
        df_furnace['Plant_average_feed_rate_Coil'] = df_furnace["DMCTF_feed"]/(df_furnace["Number_Of_Furnaces_Online"]*4)
        
        df_furnace['Coil_CIP_Calculated'] = (-131.3081 +
                (0.0755 * df_furnace['Plant_average_feed_rate_Coil']) +
                (0.1463 * df_furnace['Ethane_Feed_Preheater_Ethane_Feed_Outlet_Pressure']) +
                (0.6819 * df_furnace['Furnace_Ethane_Feed_Preheater_Ethane_Feed_Outlet_Temperature']) +
                (0.4853 * df_furnace['Coil_Weighted_Avg_Feed_CV_opening']) +
                (0.8766 * df_furnace['Coil_Weighted_Avg_Steam_CV_opening']))
        
        df_furnace['Coil_Steam_Flow'] = (df_furnace['Coil_Avg_SHC_Ratio']*df_furnace['Plant_average_feed_rate_Coil'])
               
        df_furnace['Coil_Mixed_Feed_flow'] = df_furnace['Coil_Steam_Flow'] + df_furnace['Plant_average_feed_rate_Coil']
        
        df_furnace['Coil_Mixed_Feed_Cp'] = (
            (df_furnace['Coil_Steam_Flow'] * 2.067) + 
            (df_furnace['Plant_average_feed_rate_Coil'] * 1.909)
        ) / (df_furnace['Coil_Steam_Flow'] + df_furnace['Plant_average_feed_rate_Coil'])   
        
        df_furnace['Coil_Mixed_Feed_Mol_wt'] = (
            df_furnace['Coil_Mixed_Feed_flow'] / 
            (
                (df_furnace['Plant_average_feed_rate_Coil'] / df_furnace["Furnace_Feed_Average_Molecular_Wt"]) + 
                (df_furnace['Coil_Steam_Flow'] / 18.0)
            )
        )
        
        df_furnace['Coil_Volumetric_Flow'] = (
            df_furnace['Coil_Mixed_Feed_flow']
        ) / (
            ((df_furnace['Coil_CIP_Calculated'] + 101.325) * 
              0.00982963 * df_furnace['Coil_Mixed_Feed_Mol_wt'] ) / 
            (0.08206 * (df_furnace['Coil_Weighted_Avg_Coil_Mixed_Feed_Inlet_Temperature'] + 273.15))
        )
        
        df_furnace['Coil_CIP_Corrected_atma'] = np.where(
            (df_furnace['Coil_CIP_Calculated'] / 101.325 + 1) < 5,
            (df_furnace['Coil_CIP_Calculated'] / 101.325 + 1) - 
            (df_furnace['Coil_Volumetric_Flow'] * 144 / 1309.83) * 0.00986923,
            (df_furnace['Coil_CIP_Calculated'] / 101.325 + 1) - 
            (df_furnace['Coil_Volumetric_Flow'] * 131 / 1209.52) * 0.00986923
        )
        return df_furnace

    selected_row = COT_calculation(selected_row)

    Delta_CGC_Suction_Pressure_old = 0

    selected_row['Corrected_COP_Furnace'] = selected_row['Coil_Weighted_Avg_COP'] + Delta_CGC_Suction_Pressure_old

    selected_row['Furnace_Effluent_C2H6'] = (selected_row['DMCTF_feed']/1000)*(selected_row['Furnace_Normalised_Feed_C2H6_Wt']/100) * (1 - selected_row['Furnace_conversion'])

    selected_row['Furnace_Effluent_C2H6_wt%'] =(selected_row['Furnace_Effluent_C2H6']/(selected_row['DMCTF_feed']/1000))*100

    selected_row['Coil_Avg_COT_actual'] = ((
        0.937913371 * (selected_row['Coil_CIP_Corrected_atma'] - 0.3) -
        2.413045433 * (selected_row['Corrected_COP_Furnace'] / 101.325 + 1 - 0.2) +
        2.774285758 * selected_row['Coil_Avg_SHC_Ratio'] +
        0.002253435 * selected_row['Plant_average_feed_rate_Coil'] -
        0.463411867 * selected_row['Furnace_Normalised_Feed_C3H8_Wt'] +
        0.674941411 * selected_row['Furnace_Normalised_Feed_C2H6_Wt'] +
        337.8851416 - selected_row['Furnace_Effluent_C2H6_wt%']
        ))/0.451606991


    selected_row_updated = COT_calculation(selected_row_updated)

    Delta_CGC_Suction_Pressure = selected_row_updated["CGC_STAGE_1_SUCTION_PRESSURE"] - selected_row["CGC_STAGE_1_SUCTION_PRESSURE"]

    selected_row_updated['Corrected_COP_Furnace'] = selected_row_updated['Coil_Weighted_Avg_COP'] + Delta_CGC_Suction_Pressure
    
    if ((selected_row_updated['DMCTF_feed'].iloc[0] / 1000) - selected_row_updated['Fresh_ethane_feed'].iloc[0])>70:
        selected_row_updated['Fresh_ethane_feed'] = (selected_row_updated['DMCTF_feed']/1000) - 70
    
    selected_row_updated['Furnace_conversion'] = ((selected_row_updated['DMCTF_feed']/1000)*(selected_row_updated['Furnace_Normalised_Feed_C2H6_Wt']/100) - 
                                (selected_row_updated['DMCTF_feed']/1000-selected_row_updated['Fresh_ethane_feed']))/((selected_row_updated['DMCTF_feed']/1000)*selected_row_updated['Furnace_Normalised_Feed_C2H6_Wt']/100)

    selected_row_updated['Furnace_Effluent_C2H6'] = (selected_row_updated['DMCTF_feed']/1000)*(selected_row_updated['Furnace_Normalised_Feed_C2H6_Wt']/100) * (1 - selected_row_updated['Furnace_conversion'])

    selected_row_updated['Furnace_Effluent_C2H6_wt%'] =(selected_row_updated['Furnace_Effluent_C2H6']/(selected_row_updated['DMCTF_feed']/1000))*100

    selected_row_updated['Coil_Avg_COT'] = ((
        0.937913371 * (selected_row_updated['Coil_CIP_Corrected_atma'] - 0.3) -
        2.413045433 * (selected_row_updated['Corrected_COP_Furnace'] / 101.325 + 1 - 0.2) +
        2.774285758 * selected_row_updated['Coil_Avg_SHC_Ratio'] +
        0.002253435 * selected_row_updated['Plant_average_feed_rate_Coil'] -
        0.463411867 * selected_row_updated['Furnace_Normalised_Feed_C3H8_Wt'] +
        0.674941411 * selected_row_updated['Furnace_Normalised_Feed_C2H6_Wt'] +
        337.8851416 - selected_row_updated['Furnace_Effluent_C2H6_wt%']
        ))/0.451606991

    delta_COT = selected_row_updated['Coil_Avg_COT'] -selected_row['Coil_Avg_COT_actual']

    selected_row_updated['Coil_Avg_COT'] = selected_row['Coil_Avg_COT'] + delta_COT


    # CGC stage 5 pressure prediction updation
    y_col = "CGC_5TH_STG_DISCH_PRES"
    selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
    )

    #Fifth stage discharge pressure user based value
    y_col = "CGC_5TH_STG_DISCH_PRES"
    selected_row_updated = update_parameter_from_user_input(
        y_col=y_col,
        user_input_df=user_input_df,
        selected_row_updated=selected_row_updated
    )

    # 1. Safe Constraint Check
    constraint_hit = False
    param_name = "CGC_5TH_STG_DISCH_PRES"

    # Check if parameter exists in constraints_df before accessing
    mask = constraints_df["Parameter"] == param_name
    if mask.any():
        limit = constraints_df.loc[mask, "user input value"].values[0]
        if selected_row_updated[param_name].values[0] > limit:
            selected_row_updated[param_name] = "constraints hits: Reduce the DMCTF"
            constraint_hit = True
            Actual_vs_estimated = pd.concat([selected_row, selected_row_updated], axis=0)
            Actual_vs_estimated.index = ["actual", "estimated"]
            styled = Actual_vs_estimated
            styled.to_excel("..\\Results\\Actual_vs_estimated what if.xlsx", engine='openpyxl')
    else:
        print(f"⚠️ Warning: Parameter '{param_name}' not found in constraints_df")

    if not constraint_hit:
        # CGC power prediction
        y_col = "CGC_Power_KW"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details)
        
        # CGC Turbine HP steam flow
        y_col = "CGC_Turbine_HP_Steam_flow"
        selected_row_updated = predict_and_update_with_kalman(
            y_col=y_col,
            selected_row_updated=selected_row_updated,
            config_df_model_details=config_df_model_details
        )
        
        # PRC 1st stage suction flow prediction
        mask = (selected_row_updated['PRC_turbine_steam_flow'] < constraints_df[constraints_df["Parameter"]=="PRC_turbine_steam_flow"]["user input value"].values[0]) & (selected_row_updated['PRC_turbine_RPM'] < constraints_df[constraints_df["Parameter"]=="PRC_turbine_RPM"]["user input value"].values[0])
        selected_row_updated.loc[mask, 'PRC_turbine_RPM'] = constraints_df[constraints_df["Parameter"]=="PRC_turbine_RPM"]["Max vlaue"].values[0] 
        
        #PRC_turbine Turbine speed user based input
        y_col = "PRC_turbine_RPM"
        selected_row_updated = update_parameter_from_user_input(
            y_col=y_col,
            user_input_df=user_input_df,
            selected_row_updated=selected_row_updated
        )
        
        y_col = "PRC_1ST_STAGE_Suction_FLOW"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )
        
        # PRC 1st stage suction Pressure prediction 
        y_col = "PRC_1ST_STAGE_Suction_PRESSURE"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )
        
        #PRC_1ST_STAGE_Suction_PRESSURE user based input
        y_col = "PRC_1ST_STAGE_Suction_PRESSURE"
        selected_row_updated = update_parameter_from_user_input(
            y_col=y_col,
            user_input_df=user_input_df,
            selected_row_updated=selected_row_updated
        )
        
        # PRC PRC_2nd_stage_drum_Overhead_Flow prediction
        y_col = "PRC_2nd_stage_drum_Overhead_Flow"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )
        
        def PRC_section_power(df):
            Density_1st_stage =[]
            rho_1st_stage_flow = []
            for i in range(len(df)):
                T_K = df["PRC_1ST_STAGE_Suction_TEMP"].iloc[i] + 273.15
                P_Pa = df["PRC_1ST_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5
                rho_1st_stage = PropsSI('D', 'T', T_K, 'P', P_Pa, 'Propylene')
                volumetric_flow = df["PRC_1ST_STAGE_Suction_FLOW"].iloc[i] * 1000 / rho_1st_stage
                rho_1st_stage_flow.append(volumetric_flow)
                Density_1st_stage.append(rho_1st_stage)
                   
            df["PRC_Density_1st_stage"] = Density_1st_stage
            df["PRC VOL FLOW 1ST STAGE"] = rho_1st_stage_flow

            Density_2nd_stage =[]
            rho_2nd_stage_flow = []
            for i in range(len(df)):
                T_K = df["PRC_2nd_stage_drum_Overhead_Temp"].iloc[i] + 273.15
                P_Pa = df["PRC_2ND_STAGE_Suction_PRESSURE"].iloc[i]* 1000 + 1e5
                rho_2nd_stage = PropsSI('D', 'T', T_K, 'P', P_Pa, 'Propylene')
                volumetric_flow = (df["PRC_1ST_STAGE_Suction_FLOW"].iloc[i] + df["PRC_2nd_stage_drum_Overhead_Flow"].iloc[i]) * 1000 / rho_2nd_stage
                rho_2nd_stage_flow.append(volumetric_flow)
                Density_2nd_stage.append(rho_2nd_stage)
                
            df["PRC_Density_2nd_stage"] = Density_2nd_stage   
            df["PRC VOL FLOW 2ND STAGE"] = rho_2nd_stage_flow

            Density_3rd_stage =[]
            rho_3rd_stage_flow = []

            for i in range(len(df)):
                T_K = df["PRC_3RD_STAGE_Suction_TEMP"].iloc[i] + 273.15
                P_Pa = df["PRC_3RD_STAGE_Suction_PRESSURE"].iloc[i] * 1000 + 1e5
                rho_3rd_stage = PropsSI('D', 'T', T_K, 'P', P_Pa, 'Propylene')
                volumetric_flow = df["PRC_3RD_STAGE_Suction_FLOW"].iloc[i]  * 1000 / rho_3rd_stage
                rho_3rd_stage_flow.append(volumetric_flow)
                Density_3rd_stage.append(rho_3rd_stage)

            df["PRC_Density_3rd_stage"] = Density_3rd_stage
            df["PRC VOL FLOW 3RD STAGE"] = rho_3rd_stage_flow

            #Compressor power calculation based on isentropic enthalpy at outlet pressure, keeping entropy constant (i.e., isentropic compression).
            eta = 0.70  # Assume Compressor efficiency
            PRC_1st_stage_comp_estimated_power =[]
            # Step 2: Get inlet enthalpy and entropy
            for i in range(len(df)):
                h1 = PropsSI('H', 'T',df["PRC_1ST_STAGE_Suction_TEMP"].iloc[i] + 273.15 , 'P', df["PRC_1ST_STAGE_Suction_PRESSURE"].iloc[i] * 1000+ 1e5, 'Propylene')  # J/kg
                s1 = PropsSI('S', 'T',df["PRC_1ST_STAGE_Suction_TEMP"].iloc[i] + 273.15 , 'P', df["PRC_1ST_STAGE_Suction_PRESSURE"].iloc[i] * 1000+ 1e5, 'Propylene')  # J/kg.K
                #Get isentropic outlet enthalpy (h2s at P2, s1)
                T2s = PropsSI('T', 'P', df["PRC_1ST_STAGE_Discharge_PRESSURE"].iloc[i]* 1000 + 1e5, 'S', s1, 'Propylene')  # isentropic outlet temp
                h2s = PropsSI('H', 'P', df["PRC_1ST_STAGE_Discharge_PRESSURE"].iloc[i]* 1000+ 1e5, 'S', s1, 'Propylene')  # J/kg
                h2 = h1 + (h2s - h1) / eta
                power = ((df["PRC_1ST_STAGE_Suction_FLOW"].iloc[i] * 1000)/3600) * (h2 - h1)/1e6  # KW
                PRC_1st_stage_comp_estimated_power.append(power)
                
            df["PRC_1st_stage_comp_estimated_power_MW"] = PRC_1st_stage_comp_estimated_power

            # 2nd stage compressor power
            PRC_2nd_stage_comp_estimated_power =[]
            # Step 2: Get inlet enthalpy and entropy
            for i in range(len(df)):
                h1 = PropsSI('H', 'T',df["PRC_2nd_stage_drum_Overhead_Temp"].iloc[i] + 273.15 , 'P', df["PRC_2ND_STAGE_Suction_PRESSURE"].iloc[i] * 1000+ 1e5, 'Propylene')  # J/kg
                s1 = PropsSI('S', 'T',df["PRC_2nd_stage_drum_Overhead_Temp"].iloc[i] + 273.15 , 'P', df["PRC_2ND_STAGE_Suction_PRESSURE"].iloc[i] * 1000+ 1e5, 'Propylene')  # J/kg.K
                #Get isentropic outlet enthalpy (h2s at P2, s1)
                T2s = PropsSI('T', 'P', df["PRC_3RD_STAGE_Suction_PRESSURE"].iloc[i]* 1000 + 1e5, 'S', s1, 'Propylene')  # isentropic outlet temp
                h2s = PropsSI('H', 'P', df["PRC_3RD_STAGE_Suction_PRESSURE"].iloc[i]* 1000+ 1e5, 'S', s1, 'Propylene')  # J/kg
                h2 = h1 + (h2s - h1) / eta
                power = (((df["PRC_2nd_stage_drum_Overhead_Flow"].iloc[i] + df["PRC_1ST_STAGE_Suction_FLOW"].iloc[i]) * 1000)/3600) * (h2 - h1)/1e6  # MW
                PRC_2nd_stage_comp_estimated_power.append(power)
                
            df["PRC_2nd_stage_comp_estimated_power_MW"] = PRC_2nd_stage_comp_estimated_power

            # 3rd stage compressor power
            PRC_3rd_stage_comp_estimated_power =[]
            # Step 2: Get inlet enthalpy and entropy
            for i in range(len(df)):
                h1 = PropsSI('H', 'T',df["PRC_3RD_STAGE_Suction_TEMP"].iloc[i] + 273.15 , 'P', df["PRC_3RD_STAGE_Suction_PRESSURE"].iloc[i] * 1000+ 1e5, 'Propylene')  # J/kg
                s1 = PropsSI('S', 'T',df["PRC_3RD_STAGE_Suction_TEMP"].iloc[i] + 273.15 , 'P', df["PRC_3RD_STAGE_Suction_PRESSURE"].iloc[i] * 1000+ 1e5, 'Propylene')  # J/kg.K
                #Get isentropic outlet enthalpy (h2s at P2, s1)
                T2s = PropsSI('T', 'P', df["PRC_3RD_STAGE_Discharge_PRESSURE"].iloc[i]* 1000 + 1e5, 'S', s1, 'Propylene')  # isentropic outlet temp
                h2s = PropsSI('H', 'P', df["PRC_3RD_STAGE_Discharge_PRESSURE"].iloc[i]* 1000+ 1e5, 'S', s1, 'Propylene')  # J/kg
                h2 = h1 + (h2s - h1) / eta
                power = ((df["PRC_3RD_STAGE_Suction_FLOW"].iloc[i]* 1000)/3600) * (h2 - h1)/1e6  # MW
                PRC_3rd_stage_comp_estimated_power.append(power)
                
            df["PRC_3rd_stage_comp_estimated_power_MW"] = PRC_3rd_stage_comp_estimated_power

            df["PRC_Total_estimated_power_MW"] = df["PRC_1st_stage_comp_estimated_power_MW"]+df["PRC_2nd_stage_comp_estimated_power_MW"]+df["PRC_3rd_stage_comp_estimated_power_MW"]

            return df
        
        selected_row_updated = PRC_section_power(selected_row_updated)
        
        def PRC_turbine_extraction_steam_flow_prediction (df):
            PRC_turbine_current_steam_enthalpy_KJ_Kg = []
            PRC_turbine_current_steam_entropy_KJ_KgK =[]
            PRC_turbine_current_outlet_ethalpy_KJ_Kg =[]
            PRC_turbine_current_outlet_isentropic_ethalpy_KJ_Kg =[]
            PRC_turbine_current_power_gen_extraction_MW = []
            PRC_turbine_current_power_gen_exhaust_MW =[]
            PRC_turbine_current_Turbine_power_MW_based_on_EE = []
            PRC_turbine_current_Turbine_power_MW_based_on_steam_flow = []
            PRC_turbine_current_Specific_steam_consumption_MT_MW =[]
            #turbine_efficiency =[]
            
            for i in range(len(df)):
                Steam_flow_TPH = df['PRC_turbine_steam_flow'].iloc[i]
                Condensate_flow_TPH = df['PRC_turbine_condensate_flow'].iloc[i]
                Extraction_flow_TPH = df['PRC_turbine_Extraction_flow'].iloc[i]
                
                Steam_flow_Kg_hr       = Steam_flow_TPH *1000
                Extraction_flow_Kg_hr  = Extraction_flow_TPH *1000
                Condensate_flow_Kg_hr  = Condensate_flow_TPH *1000
            
                # Steam Inlet conditions
                P_steam = df['PRC_turbine_Steam_pressure'].iloc[i]*1000   # Pa
                T_steam = df['PRC_turbine_Steam_Temp'].iloc[i] +273.15   # K
                T_sat_steam = PropsSI('T', 'P', P_steam, 'Q', 1, 'Water') - 273.15 # degC
            
                # Extraction pressure
                Pe = df['PRC_turbine_Extraction_Pressure'].iloc[i]*1000      # Pa 
                T_sat_extraction = PropsSI('T', 'P', Pe, 'Q', 1, 'Water') # K
            
                # Condenser pressure
                Pc = df['PRC_turbine_Condensate_Pressure'].iloc[i]*1000
                Tc_actual = df['PRC_turbine_Condensate_Temperature'].iloc[i] +273.15  # K (actual exhaust steam temp)
                T_sat_condensate = PropsSI('T', 'P', Pc, 'Q', 0, 'Water') # degC
                
                # Steam (inlet) Enthalpy calculation 
                h_steam = PropsSI('H', 'P', P_steam, 'T', T_steam,'Water')/1000   # kJ/kg
                s_steam = PropsSI('S', 'P', P_steam, 'T', T_steam, 'Water')/1000  # KJ/kg·K
                
                # Actual outlet enthalpies
                # Actual outlet enthalpies
                # he = PropsSI('H', 'P', Pe, 'T', Te_actual, 'Water')/1000  # Extracted steam (actual)
                he = PropsSI('H', 'P', Pe, 'T', T_sat_extraction + 0.01, 'Water')/1000  # Extracted steam (actual)
                #hc = PropsSI('H', 'P', Pc, 'T', Tc_actual, 'Water')/1000  # Condenser outlet (actual)
                hc_liquid = PropsSI('H', 'P', Pc, 'T', T_sat_condensate - 0.01, 'Water')/1000  # Condenser outlet (actual)
                dryness_fraction = 0.92
                hc_vapor = PropsSI('H', 'P', Pc, 'T', T_sat_condensate + 0.01, 'Water')/1000  # Condenser outlet (actual)
            
                hc = hc_liquid + hc_vapor*dryness_fraction
            
                Net_heat_release = Steam_flow_Kg_hr*h_steam -Extraction_flow_Kg_hr*he - Condensate_flow_Kg_hr*hc
                power_gen_extraction = Extraction_flow_Kg_hr*(h_steam-he)/3600/1000
                power_gen_exhaust = Condensate_flow_Kg_hr*(h_steam-hc)/3600/1000
                Turbine_power_MW_EE = power_gen_extraction + power_gen_exhaust
                Specific_steam_consumption = Steam_flow_TPH/(Turbine_power_MW_EE) # MT/MW
            
                def isentropic_enthalpy(P_target, s_in):
                    # Keep everything in J/kg·K
                    s_f = PropsSI("S", "P", P_target, "Q", 0, "Water")/1000
                    s_g = PropsSI("S", "P", P_target, "Q", 1, "Water")/1000
                
                    if s_f < s_in < s_g:
                        x = (s_in - s_f) / (s_g - s_f)
                        h_f = PropsSI("H", "P", P_target, "Q", 0, "Water")
                        h_g = PropsSI("H", "P", P_target, "Q", 1, "Water")
                        h_iso = h_f + x * (h_g - h_f)
                    else:
                        h_iso = PropsSI("H", "P", P_target, "S", s_in, "Water")
                
                    return h_iso / 1000  # Convert to kJ/kg
            
            
                # Isentropic outlet enthalpies
                he_s = isentropic_enthalpy(Pe, s_steam)
                hc_s = isentropic_enthalpy(Pc, s_steam)
                
                # Mass-weighted outlet enthalpies
                h2_actual = (Extraction_flow_Kg_hr * he + Condensate_flow_Kg_hr * hc) / Steam_flow_Kg_hr
                h2s_ideal = (Extraction_flow_Kg_hr  * he_s + Condensate_flow_Kg_hr * hc_s) / Steam_flow_Kg_hr
                
                # Turbine isentropic efficiency
                efficiency = (h_steam - h2_actual) / (h_steam - h2s_ideal)*100
                
                turbine_power_MW_SF = (h_steam - h2_actual) * (Steam_flow_Kg_hr / (3600*1000))  # Convert kg/hr to kg/s
                
                PRC_turbine_current_steam_enthalpy_KJ_Kg.append(h_steam)
                PRC_turbine_current_steam_entropy_KJ_KgK.append(s_steam)
                PRC_turbine_current_outlet_ethalpy_KJ_Kg.append(h2_actual)
                PRC_turbine_current_outlet_isentropic_ethalpy_KJ_Kg.append(h2s_ideal)
                PRC_turbine_current_power_gen_extraction_MW.append(power_gen_extraction)
                PRC_turbine_current_power_gen_exhaust_MW.append(power_gen_exhaust)
                PRC_turbine_current_Turbine_power_MW_based_on_EE.append(Turbine_power_MW_EE)
                PRC_turbine_current_Turbine_power_MW_based_on_steam_flow.append(turbine_power_MW_SF)
                PRC_turbine_current_Specific_steam_consumption_MT_MW.append(Specific_steam_consumption)
                #turbine_efficiency.append(efficiency)
                
            df["PRC_turbine_current_steam_enthalpy_KJ_Kg"] = PRC_turbine_current_steam_enthalpy_KJ_Kg
            df["PRC_turbine_current_steam_entropy_KJ_KgK"] = PRC_turbine_current_steam_entropy_KJ_KgK
            df["PRC_turbine_current_outlet_ethalpy_KJ_Kg"] = PRC_turbine_current_outlet_ethalpy_KJ_Kg
            df["PRC_turbine_current_outlet_isentropic_ethalpy_KJ_Kg"] = PRC_turbine_current_outlet_isentropic_ethalpy_KJ_Kg
            df["PRC_turbine_current_power_gen_extraction_MW"] = PRC_turbine_current_power_gen_extraction_MW
            df["PRC_turbine_current_power_gen_exhaust_MW"] = PRC_turbine_current_power_gen_exhaust_MW
            df["PRC_turbine_current_Turbine_power_MW_based_on_EE"] = PRC_turbine_current_Turbine_power_MW_based_on_EE
            df["PRC_turbine_current_Turbine_power_MW_based_on_steam_flow"] = PRC_turbine_current_Turbine_power_MW_based_on_steam_flow
            df["PRC_turbine_current_Specific_steam_consumption_MT_MW"] = PRC_turbine_current_Specific_steam_consumption_MT_MW
    #df["turbine_efficiency"] = turbine_efficiency
        
            PRC_turbine_optimized_extraction = []
            PRC_turbine_calculated_steam_flow = []
            PRC_turbine_matched_power_EE = []
            PRC_turbine_matched_power_SF = []
            PRC_turbine_matched_h2_actual = []

            def match_actual_power(row):
                try:
                    # Steam inlet enthalpy
                    P_steam = row["PRC_turbine_Steam_pressure"] * 1000  # Pa
                    T_steam = row["PRC_turbine_Steam_Temp"] + 273.15    # K
                    h_steam = PropsSI("H", "P", P_steam, "T", T_steam, "Water") / 1000  # kJ/kg
                 
                    # Actual extracted steam enthalpy (he)
                    Pe = row["PRC_turbine_Extraction_Pressure"] * 1000  # Pa
                    # Te_actual = row["Extraction Temperature"] + 273.15  # K
                    T_sat_extraction = PropsSI('T', 'P', Pe, 'Q', 1, 'Water') # K
                    he = PropsSI('H', 'P', Pe, 'T', T_sat_extraction + 0.01, 'Water')/1000  # Extracted steam (actual)
                    
                    # Actual condenser steam enthalpy (hc)
                    Pc = row["PRC_turbine_Condensate_Pressure"] * 1000  # Pa
                    # Tc_actual = row["Condensate Temperature"] + 273.15  # K
                    T_sat_condensate = PropsSI('T', 'P', Pc, 'Q', 0, 'Water') # degC
                    hc_liquid = PropsSI('H', 'P', Pc, 'T', T_sat_condensate - 0.01, 'Water')/1000  # Condenser outlet (actual)
                    dryness_fraction = 0.92
                    hc_vapor = PropsSI('H', 'P', Pc, 'T', T_sat_condensate + 0.01, 'Water')/1000  # Condenser outlet (actual)
                
                    hc = hc_liquid + hc_vapor*dryness_fraction
                
                    condensate_flow_TPH = row["PRC_turbine_condensate_flow"]
                    condensate_flow_Kg_hr = condensate_flow_TPH * 1000
                    actual_power = row["PRC_Total_estimated_power_MW"]
                
                    def objective(extraction_flow_TPH):
                        extraction_flow_Kg_hr = extraction_flow_TPH * 1000
                        steam_flow_Kg_hr = extraction_flow_Kg_hr + condensate_flow_Kg_hr
                
                        power = ((extraction_flow_Kg_hr * (h_steam - he)) + 
                                 (condensate_flow_Kg_hr * (h_steam - hc))) / 3600 / 1000
                        return (power - actual_power) ** 2
                
                    result = minimize_scalar(objective, bounds=(10, 350), method='bounded')
                
                    if result.success:
                        ef_opt = result.x
                        ef_Kg_hr = ef_opt * 1000
                        sf_opt = ef_opt + condensate_flow_TPH
                        sf_Kg_hr = sf_opt * 1000
                        # Matched power via energy balance
                        power_matched_EE = ((ef_Kg_hr * (h_steam - he)) + (condensate_flow_Kg_hr * (h_steam - hc))) / 3600 / 1000
        
                        # Mass-weighted outlet enthalpy
                        h2_actual = (ef_Kg_hr * he + condensate_flow_Kg_hr * hc) / sf_Kg_hr
        
                        # Power via inlet/outlet enthalpy and total flow
                        power_matched_SF = (h_steam - h2_actual) * (sf_Kg_hr / 3600 / 1000)
        
                        return ef_opt, sf_opt, power_matched_EE, power_matched_SF, h2_actual
                    else:
                        return (row["PRC_turbine_Extraction_flow"], row["PRC_turbine_steam_flow"],
                                row["PRC_turbine_current_Turbine_power_MW_based_on_EE"], row["PRC_turbine_current_Turbine_power_MW_based_on_steam_flow"],
                                None)
                except Exception as e:
                    print(f"Error at index {row.name}: {e}")
                    return (row["PRC_turbine_Extraction_flow"], row["PRC_turbine_steam_flow"],
                            row["PRC_turbine_current_Turbine_power_MW_based_on_EE"], row["PRC_turbine_current_Turbine_power_MW_based_on_steam_flow"],
                            None)
                
            # Loop and apply
            for _, row in df.iterrows():
                ef, sf, power_EE, power_SF, h2 = match_actual_power(row)
                PRC_turbine_optimized_extraction.append(ef)
                PRC_turbine_calculated_steam_flow.append(sf)
                PRC_turbine_matched_power_EE.append(power_EE)
                PRC_turbine_matched_power_SF.append(power_SF)
                PRC_turbine_matched_h2_actual.append(h2)
        
            # Save to DataFrame
            df["PRC_turbine_Optimized_Extraction_flow_TPH"] = PRC_turbine_optimized_extraction
            df["PRC_turbine_Calculated_Steam_flow_TPH"] = PRC_turbine_calculated_steam_flow
            df["PRC_turbine_Matched_Turbine_power_MW_EE"] = PRC_turbine_matched_power_EE
            df["PRC_turbine_Matched_Turbine_power_MW_SF"] = PRC_turbine_matched_power_SF
            df["PRC_turbine_Matched_h2_actual_KJ_Kg"] = PRC_turbine_matched_h2_actual
            df["Power_Error"] = (
                df["PRC_turbine_Matched_Turbine_power_MW_EE"] -
                df["PRC_Total_estimated_power_MW"]
            )
            df["Power_EE_vs_SF_Diff"] = (
                df["PRC_turbine_Matched_Turbine_power_MW_EE"] -
                df["PRC_turbine_Matched_Turbine_power_MW_SF"]
            )
            df["Devaiation in steam flow (Simulated-actual)"] = df["PRC_turbine_Calculated_Steam_flow_TPH"]- df["PRC_turbine_steam_flow"]
            df["Devaiation in extraction (Simulated-actual)"] = df["PRC_turbine_Optimized_Extraction_flow_TPH"]- df["PRC_turbine_Extraction_flow"]
            df["Specific_steam_consumption_MT_MW_updated"] = df["PRC_turbine_Calculated_Steam_flow_TPH"] / df["PRC_Total_estimated_power_MW"]

            return df
        
        selected_row_updated = PRC_turbine_extraction_steam_flow_prediction (selected_row_updated)
        
        # ERC ERC_2nd_stage_drum_Overhead_Flow prediction
        mask = (selected_row_updated['ERC_turbine_steam_flow'] < constraints_df[constraints_df["Parameter"]=='ERC_turbine_steam_flow']["user input value"].values[0]) & (selected_row_updated['ERC_turbine_Speed'] < constraints_df[constraints_df["Parameter"]=="ERC_turbine_Speed"]["user input value"].values[0])
        selected_row_updated.loc[mask, 'ERC_turbine_Speed'] =constraints_df[constraints_df["Parameter"]=="ERC_turbine_Speed"]["Max vlaue"].values[0] 
        
        #ERC_turbine_Speed user based input
        y_col = "ERC_turbine_Speed"
        selected_row_updated = update_parameter_from_user_input(
            y_col=y_col,
            user_input_df=user_input_df,
            selected_row_updated=selected_row_updated
        )
        
        y_col = "ERC_2nd_stage_drum_Overhead_Flow"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )

        # KT1701 steam flow prediction
        y_col = "ERC_turbine_steam_flow"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )
        
        # ERC power prediction through Steam flow
        y_col = "ERC_power"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )
        
        #ERC first stage suction flow prediction
        y_col = "ERC_1ST_STAGE_Suction_FLOW"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )

        # ERC first stage suction pressure prediction
        y_col = "ERC_1ST_STAGE_Suction_PRESSURE"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )
        
        #ERC_1ST_STAGE_Suction_PRESSURE user based input
        y_col = "ERC_1ST_STAGE_Suction_PRESSURE"
        selected_row_updated = update_parameter_from_user_input(
            y_col=y_col,
            user_input_df=user_input_df,
            selected_row_updated=selected_row_updated
        )
        
        selected_row_updated["Total_Power_(KW)"]= selected_row_updated["CGC_Power_KW"] + selected_row_updated["PRC_Total_estimated_power_MW"]*1000 + selected_row_updated["ERC_power"]
        selected_row_updated["Total_required_steam_flow_(TPH)"] = selected_row_updated["CGC_Turbine_HP_Steam_flow"] + selected_row_updated["PRC_turbine_Calculated_Steam_flow_TPH"] + selected_row_updated["ERC_turbine_steam_flow"]
        
        # Ethylene loss to fuel prediction
        y_col = "TOTAL_ETHYLENE_LOSS_to_fuel"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )
        
        # Ethylene product flow prediction
        y_col = "Ethylene_product_flow"
        selected_row_updated = predict_and_update_with_kalman(
        y_col=y_col,
        selected_row_updated=selected_row_updated,
        config_df_model_details=config_df_model_details
        )
        
        Actual_vs_estimated = pd.concat([selected_row, selected_row_updated], axis=0)
        Actual_vs_estimated.index = ["actual", "estimated"]
        
        def color_diff(val):
            color = 'green' if val > 0 else 'red' if val < 0 else ''
            return f'background-color: {color}' if color else ''
        
        diff = Actual_vs_estimated.loc['estimated'] - Actual_vs_estimated.loc['actual']
        Actual_vs_estimated["Timestamp"] = user_time
        styled = Actual_vs_estimated.style.apply(lambda _: diff.map(color_diff), axis=1)
        styled.to_excel("..\\Results\\Actual_vs_estimated what if.xlsx", engine='openpyxl')
        
        return styled  

