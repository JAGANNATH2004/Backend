from typing import List
from pydantic import BaseModel

class PerformanceItem(BaseModel):
    product_id: str
    product_name: str
    quantity_sold: float
    unit: str
    total_revenue: float

class ReorderItem(BaseModel):
    product_id: str
    product_name: str
    current_stock: float
    min_threshold: float
    unit: str
    days_of_coverage: int
    recommended_quantity: float

class DailySalesPoint(BaseModel):
    day_name: str
    amount: float

class ReportResponse(BaseModel):
    time_range: str
    total_revenue: float
    transaction_count: int
    units_sold: float
    best_selling: List[PerformanceItem]
    slow_moving: List[PerformanceItem]
    reorders: List[ReorderItem]
    sales_trend: List[DailySalesPoint]

