from datetime import datetime, date, timedelta
from typing import Dict, List
from app.services.inventory_service import InventoryService
from app.models.reports import (
    ReportResponse,
    PerformanceItem,
    ReorderItem,
    DailySalesPoint,
)

class ReportsService:
    @staticmethod
    def get_report(business_id: str, time_range: str = "today") -> ReportResponse:
        products = InventoryService.get_products(business_id)
        all_movements = InventoryService.get_movements(business_id, limit=200)

        now = datetime.utcnow()
        today = date.today()

        # Filter sales movements by timeframe
        sale_movements = [m for m in all_movements if m.type == "sale"]
        filtered_sales = []

        for m in sale_movements:
            try:
                m_dt = datetime.fromisoformat(m.timestamp.replace("Z", "+00:00"))
                m_date = m_dt.date()
            except Exception:
                m_date = today

            if time_range == "today":
                if m_date == today:
                    filtered_sales.append(m)
            elif time_range == "thisWeek":
                if m_date >= today - timedelta(days=7):
                    filtered_sales.append(m)
            elif time_range == "thisMonth":
                if m_date.year == today.year and m_date.month == today.month:
                    filtered_sales.append(m)
            else:
                filtered_sales.append(m)

        total_revenue = sum(m.quantity * m.price for m in filtered_sales)
        transaction_count = len(filtered_sales)
        units_sold = sum(m.quantity for m in filtered_sales)

        # Performance map
        product_qty_map: Dict[str, float] = {}
        product_rev_map: Dict[str, float] = {}
        product_name_map: Dict[str, str] = {}
        product_unit_map: Dict[str, str] = {}

        for m in filtered_sales:
            pid = m.product_id
            product_qty_map[pid] = product_qty_map.get(pid, 0.0) + m.quantity
            product_rev_map[pid] = product_rev_map.get(pid, 0.0) + (m.quantity * m.price)
            product_name_map[pid] = m.product_name
            product_unit_map[pid] = m.unit

        best_selling: List[PerformanceItem] = []
        for pid, qty in product_qty_map.items():
            best_selling.append(
                PerformanceItem(
                    product_id=pid,
                    product_name=product_name_map.get(pid, "Product"),
                    quantity_sold=qty,
                    unit=product_unit_map.get(pid, "Units"),
                    total_revenue=product_rev_map.get(pid, 0.0),
                )
            )
        best_selling.sort(key=lambda x: x.quantity_sold, reverse=True)

        slow_moving: List[PerformanceItem] = []
        for p in products:
            if p.id not in product_qty_map:
                slow_moving.append(
                    PerformanceItem(
                        product_id=p.id,
                        product_name=p.name,
                        quantity_sold=0.0,
                        unit=p.unit,
                        total_revenue=0.0,
                    )
                )

        reorders: List[ReorderItem] = []
        for p in products:
            if p.current_stock <= p.min_threshold:
                days = max(0, min(14, int(p.current_stock / 3.0))) if p.current_stock > 0 else 0
                rec_qty = max(p.min_threshold, (p.min_threshold * 2.5) - p.current_stock)
                reorders.append(
                    ReorderItem(
                        product_id=p.id,
                        product_name=p.name,
                        current_stock=p.current_stock,
                        min_threshold=p.min_threshold,
                        unit=p.unit,
                        days_of_coverage=days,
                        recommended_quantity=rec_qty,
                    )
                )

        # 7-day sales trend
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        sales_trend: List[DailySalesPoint] = []
        for i in range(6, -1, -1):
            target_date = today - timedelta(days=i)
            day_sales = sum(
                m.quantity * m.price
                for m in sale_movements
                if m.timestamp.startswith(target_date.isoformat())
            )
            day_name = day_names[target_date.weekday()]
            sales_trend.append(DailySalesPoint(day_name=day_name, amount=day_sales))

        return ReportResponse(
            time_range=time_range,
            total_revenue=total_revenue,
            transaction_count=transaction_count,
            units_sold=units_sold,
            best_selling=best_selling[:5],
            slow_moving=slow_moving[:5],
            reorders=reorders,
            sales_trend=sales_trend,
        )

