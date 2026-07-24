"""
backend/app/services/overview_service.py
============================================
GET /api/overview is pure aggregation (dataset + saved-model inventories) —
no per-model computation, no state. Both train-set and test-set metrics are
read straight from the registry (captured once at training time in
training_service.py::_finish()) — there is no live recompute here anymore.
An earlier version of this file had a GET /models/{name}/performance
endpoint that recomputed R² live over the full stored dataset (train rows
the model had already seen + test rows); that blended, leakage-inflated
number was retired in favor of the honest train_r2/avg_r2 pair already
captured at training time.
"""
from __future__ import annotations

from src.data.database import list_datasets_from_db, list_models_from_registry
from src.persistence.model_store import list_saved_models

from backend.app.schemas.datasets import DatasetSummary
from backend.app.schemas.overview import OverviewResponse, SavedModelSummary


def get_overview() -> OverviewResponse:
    datasets = [
        DatasetSummary(name=r[0], uploaded_at=r[1], rows=r[2], cols=r[3])
        for r in list_datasets_from_db()  # src.data.database — unchanged
    ]

    registry_by_name = {
        r["model_name"]: r for r in list_models_from_registry()  # unchanged
    }

    saved_models = []
    for m in list_saved_models():  # src.persistence.model_store — unchanged
        reg = registry_by_name.get(m["name"])
        saved_models.append(
            SavedModelSummary(
                name=m["name"],
                saved_at=m["saved_at"],
                input_dim=m["input_dim"],
                output_dim=m["output_dim"],
                algorithm=(reg["algorithm"] if reg else m.get("model_type")),
                dataset_name=reg["dataset_name"] if reg else None,
                avg_r2=reg["avg_r2"] if reg else None,
                avg_rmse=reg["avg_rmse"] if reg else None,
                avg_mae=reg["avg_mae"] if reg else None,
                train_r2=reg["train_r2"] if reg else None,
                train_rmse=reg["train_rmse"] if reg else None,
                train_mae=reg["train_mae"] if reg else None,
                x_cols=m.get("x_cols", []),
                y_cols=m.get("y_cols", []),
            )
        )

    return OverviewResponse(datasets=datasets, saved_models=saved_models)
