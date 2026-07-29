from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.schemas.overview import ClearSelectionRequest, OverviewResponse, SelectModelRequest
from backend.app.services import overview_service

router = APIRouter(tags=["overview"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview() -> OverviewResponse:
    return overview_service.get_overview()


@router.post("/overview/select-model", response_model=OverviewResponse)
def select_model(payload: SelectModelRequest) -> OverviewResponse:
    try:
        return overview_service.select_model_for_parameter(payload.parameter, payload.model_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/overview/clear-selection", response_model=OverviewResponse)
def clear_selection(payload: ClearSelectionRequest) -> OverviewResponse:
    return overview_service.clear_model_selection(payload.parameter)
