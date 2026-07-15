from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.overview import OverviewResponse
from backend.app.services import overview_service

router = APIRouter(tags=["overview"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview() -> OverviewResponse:
    return overview_service.get_overview()
