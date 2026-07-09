"""
src/whatif/model_status.py
============================
Phase-1 replacement for the Streamlit app's `models_trained` session flag
(which used to be set by running the training script): a pure file-existence
check over the 15 Kalman-model tags' 3 artifacts each
(kalman_filter_model_{tag}.pkl, scaler_X_{tag}.pkl, scaler_y_{tag}.pkl).

No retraining is implemented in Phase 1 — this module only reports whether
the artifacts required by src/whatif/engine.py are already present under
Results/Model/.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# The 15 tags src/whatif/engine.py actually invokes predict_and_update_with_kalman
# for (2 of the 18 "Model details" sheet rows, Overall_COT and
# CHG_GAS_FLOW_TO_DRYER, are present in the config but never invoked).
REQUIRED_KALMAN_TAGS = [
    "Quench_tower_overhead_temp",
    "CGC_STAGE_1_SUCTION_PRESSURE",
    "CGC_5TH_STG_DISCH_PRES",
    "CGC_Power_KW",
    "CGC_Turbine_HP_Steam_flow",
    "PRC_1ST_STAGE_Suction_FLOW",
    "PRC_1ST_STAGE_Suction_PRESSURE",
    "PRC_2nd_stage_drum_Overhead_Flow",
    "ERC_2nd_stage_drum_Overhead_Flow",
    "ERC_turbine_steam_flow",
    "ERC_power",
    "ERC_1ST_STAGE_Suction_FLOW",
    "ERC_1ST_STAGE_Suction_PRESSURE",
    "TOTAL_ETHYLENE_LOSS_to_fuel",
    "Ethylene_product_flow",
]


@dataclass
class ModelStatus:
    all_present: bool
    tags_ok: list[str]
    tags_missing: list[str]
    pkl_count: int


def _tag_artifacts(model_dir: str, tag: str) -> list[str]:
    return [
        os.path.join(model_dir, f"kalman_filter_model_{tag}.pkl"),
        os.path.join(model_dir, f"scaler_X_{tag}.pkl"),
        os.path.join(model_dir, f"scaler_y_{tag}.pkl"),
    ]


def check_models_trained(model_dir: str, required_tags: list[str] | None = None) -> ModelStatus:
    tags = required_tags if required_tags is not None else REQUIRED_KALMAN_TAGS
    tags_ok: list[str] = []
    tags_missing: list[str] = []
    pkl_count = 0

    for tag in tags:
        artifacts = _tag_artifacts(model_dir, tag)
        present = [os.path.isfile(p) for p in artifacts]
        pkl_count += sum(present)
        if all(present):
            tags_ok.append(tag)
        else:
            tags_missing.append(tag)

    return ModelStatus(
        all_present=not tags_missing,
        tags_ok=tags_ok,
        tags_missing=tags_missing,
        pkl_count=pkl_count,
    )
