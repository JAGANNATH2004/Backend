from fastapi import APIRouter, Depends
from app.database import get_current_user_id
from app.models.dashboard import DashboardSummaryResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard Aggregations"])

@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    user_id: str = Depends(get_current_user_id),
):
    return DashboardService.get_summary(business_id=user_id)

