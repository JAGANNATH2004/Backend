from fastapi import APIRouter, Depends, Query
from app.database import get_current_user_id
from app.models.reports import ReportResponse
from app.services.reports_service import ReportsService

router = APIRouter(prefix="/api/reports", tags=["Business Analytics & Reports"])

@router.get("", response_model=ReportResponse)
def get_report(
    time_range: str = Query("today", alias="range"),
    user_id: str = Depends(get_current_user_id),
):
    return ReportsService.get_report(business_id=user_id, time_range=time_range)

