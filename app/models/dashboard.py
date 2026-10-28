from typing import List, Optional
from pydantic import BaseModel
from app.models.auth import BusinessProfile
from app.models.inventory import ProductResponse, MovementResponse

class DashboardSummaryResponse(BaseModel):
    business: BusinessProfile
    today_sales: float
    today_transactions: int
    total_products: int
    low_stock_count: int
    total_stock_value: float
    recent_activity: List[MovementResponse]
    low_stock_items: List[ProductResponse]

