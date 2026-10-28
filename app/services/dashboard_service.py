from datetime import datetime, date
from app.services.auth_service import AuthService
from app.services.inventory_service import InventoryService
from app.models.dashboard import DashboardSummaryResponse

class DashboardService:
    @staticmethod
    def get_summary(business_id: str) -> DashboardSummaryResponse:
        business = AuthService.get_business_profile(business_id)
        products = InventoryService.get_products(business_id)
        movements = InventoryService.get_movements(business_id, limit=20)

        # Totals
        total_products = len(products)
        low_stock_items = [p for p in products if p.current_stock <= p.min_threshold]
        low_stock_count = len(low_stock_items)
        total_stock_value = sum(p.current_stock * p.purchase_price for p in products)

        # Today's sales
        today_str = date.today().isoformat()
        today_sales_movements = [
            m for m in movements
            if m.type == "sale" and m.timestamp.startswith(today_str)
        ]
        today_sales = sum(m.quantity * m.price for m in today_sales_movements)
        today_transactions = len(today_sales_movements)

        return DashboardSummaryResponse(
            business=business,
            today_sales=today_sales,
            today_transactions=today_transactions,
            total_products=total_products,
            low_stock_count=low_stock_count,
            total_stock_value=total_stock_value,
            recent_activity=movements[:5],
            low_stock_items=low_stock_items[:5],
        )

