from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query, UploadFile
from fastapi.responses import Response

from backend.app.schemas import what_if as schemas
from backend.app.services import what_if_service

router = APIRouter(prefix="/what-if", tags=["what-if"])


# ---------------------------------------------------------------------------
# Config / wizard / model-status (case setup)
# ---------------------------------------------------------------------------

@router.get("/config/status", response_model=schemas.ConfigStatusResponse)
def config_status() -> schemas.ConfigStatusResponse:
    return what_if_service.get_config_status()


@router.get("/config/pi-mapping", response_model=schemas.RowsResponse)
def config_pi_mapping() -> schemas.RowsResponse:
    return what_if_service.get_pi_mapping()


@router.post("/config/upload", response_model=schemas.ConfigStatusResponse)
async def config_upload(file: UploadFile) -> schemas.ConfigStatusResponse:
    return await what_if_service.upload_config(file)


@router.get("/wizard/detected-counts", response_model=schemas.DetectedCountsResponse)
def wizard_detected_counts() -> schemas.DetectedCountsResponse:
    return what_if_service.get_detected_counts()


@router.post("/wizard/generate-mapping", response_model=schemas.GenerateMappingResponse)
def wizard_generate_mapping(body: schemas.GenerateMappingRequest) -> schemas.GenerateMappingResponse:
    return what_if_service.generate_mapping(body)


@router.put("/config/mapping", response_model=schemas.RowsResponse)
def config_commit_mapping(body: schemas.MappingRowsRequest) -> schemas.RowsResponse:
    return what_if_service.commit_mapping(body)


@router.get("/config/model-mapping", response_model=schemas.ModelMappingResponse)
def config_get_model_mapping() -> schemas.ModelMappingResponse:
    return what_if_service.get_model_mapping()


@router.put("/config/model-mapping", response_model=schemas.RowsResponse)
def config_commit_model_mapping(body: schemas.MappingRowsRequest) -> schemas.RowsResponse:
    return what_if_service.commit_model_mapping(body)


@router.post("/config/export")
def config_export(body: schemas.ConfigExportRequest) -> Response:
    data, media_type, filename = what_if_service.export_config(body)
    return Response(
        content=data, media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/training-data/upload", response_model=schemas.TrainingDataUploadResponse)
async def training_data_upload(file: UploadFile) -> schemas.TrainingDataUploadResponse:
    return await what_if_service.upload_training_data(file)


@router.get("/models/status", response_model=schemas.ModelStatusResponse)
def models_status() -> schemas.ModelStatusResponse:
    return what_if_service.get_models_status()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.post("/dashboard/tag-options", response_model=schemas.TagOptionsResponse)
def dashboard_tag_options(body: schemas.TagOptionsRequest) -> schemas.TagOptionsResponse:
    return what_if_service.get_tag_options(body)


@router.get("/dashboard/dates", response_model=schemas.DatesResponse)
def dashboard_dates() -> schemas.DatesResponse:
    return what_if_service.get_dates()


@router.get("/dashboard/timestamps", response_model=schemas.TimestampsResponse)
def dashboard_timestamps(date: str = Query(...)) -> schemas.TimestampsResponse:
    return what_if_service.get_timestamps(date)


@router.get("/dashboard/baseline", response_model=schemas.BaselineResponse)
def dashboard_baseline(
    timestamp: str = Query(...),
    tags: Optional[str] = Query(None, description="Comma-separated tag list"),
) -> schemas.BaselineResponse:
    tag_list: List[str] = [t for t in (tags or "").split(",") if t]
    return what_if_service.get_baseline(timestamp, tag_list)


@router.post("/dashboard/compute", response_model=schemas.WhatIfScenarioResponse)
def dashboard_compute(body: schemas.WhatIfScenarioRequest) -> schemas.WhatIfScenarioResponse:
    return what_if_service.run_scenario(body)


@router.post("/dashboard/validation-filter", response_model=schemas.ValidationFilterResponse)
def dashboard_validation_filter(body: schemas.ValidationFilterRequest) -> schemas.ValidationFilterResponse:
    return what_if_service.run_validation_filter(body)


@router.post("/dashboard/export-csv")
def dashboard_export_csv(body: schemas.WhatIfExportCsvRequest) -> Response:
    data, media_type, filename = what_if_service.export_scenario_csv(body)
    return Response(
        content=data, media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
