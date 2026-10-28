from datetime import datetime
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_current_user_id
from app.models.inventory import DeductSaleRequest
from app.models.sales import RecordSaleRequest, SaleResponse, SaleItemResponse
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/api/sales", tags=["Sales Processing"])

@router.post("/record", response_model=SaleResponse)
def record_sale(
    req: RecordSaleRequest,
    user_id: str = Depends(get_current_user_id),
):
    if not req.items:
        raise HTTPException(status_code=400, detail="Sale must contain at least one product")

    # 1. Pre-validate stock availability for all items
    for item in req.items:
        prod = InventoryService.get_product_by_id(user_id, item.product_id)
        if not prod:
            raise HTTPException(status_code=404, detail=f"Product {item.product_name} not found")
        if item.quantity > prod.current_stock:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for {prod.name}. Available: {prod.current_stock} {prod.unit}",
            )

    # 2. Execute stock deductions
    item_responses: List[SaleItemResponse] = []
    subtotal = 0.0

    for item in req.items:
        mov = InventoryService.deduct_stock_sale(
            business_id=user_id,
            req=DeductSaleRequest(
                product_id=item.product_id,
                quantity=item.quantity,
                selling_price=item.unit_price,
                notes=req.notes or "Counter Sale",
            ),
        )
        line_subtotal = item.quantity * item.unit_price
        subtotal += line_subtotal
        item_responses.append(
            SaleItemResponse(
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                subtotal=line_subtotal,
            )
        )

    total_amount = max(0.0, subtotal - req.discount)
    sale_id = f"sale_{uuid.uuid4().hex[:8]}"
    receipt_number = f"RCP-{datetime.utcnow().strftime('%H%M%S')}"

    return SaleResponse(
        id=sale_id,
        receipt_number=receipt_number,
        items=item_responses,
        subtotal=subtotal,
        discount=req.discount,
        total_amount=total_amount,
        timestamp=datetime.utcnow().isoformat(),
        notes=req.notes or "",
    )

@router.get("", response_model=List[SaleResponse])
def get_sales(
    user_id: str = Depends(get_current_user_id),
):
    movements = InventoryService.get_movements(user_id, limit=50)
    sales_movements = [m for m in movements if m.type == "sale"]

    sales_list = []
    for idx, m in enumerate(sales_movements):
        sales_list.append(
            SaleResponse(
                id=f"sale_{m.id}",
                receipt_number=f"RCP-{1000 + idx}",
                items=[
                    SaleItemResponse(
                        product_id=m.product_id,
                        product_name=m.product_name,
                        quantity=m.quantity,
                        unit=m.unit,
                        unit_price=m.price,
                        subtotal=m.quantity * m.price,
                    )
                ],
                subtotal=m.quantity * m.price,
                discount=0.0,
                total_amount=m.quantity * m.price,
                timestamp=m.timestamp,
                notes=m.notes or "",
            )
        )
    return sales_list

