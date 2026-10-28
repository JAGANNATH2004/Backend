from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.database import get_current_user_id
from app.models.inventory import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    AddStockRequest,
    DeductSaleRequest,
    MovementResponse,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/api/inventory", tags=["Inventory Management"])

@router.get("/products", response_model=List[ProductResponse])
def get_products(
    query: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id),
):
    return InventoryService.get_products(
        business_id=user_id,
        query=query,
        category=category,
        status=status,
        sort_by=sort_by,
    )

@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: str,
    user_id: str = Depends(get_current_user_id),
):
    return InventoryService.get_product_by_id(business_id=user_id, product_id=product_id)

@router.post("/products", response_model=ProductResponse)
def create_product(
    req: ProductCreate,
    user_id: str = Depends(get_current_user_id),
):
    return InventoryService.create_product(business_id=user_id, data=req)

@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    req: ProductUpdate,
    user_id: str = Depends(get_current_user_id),
):
    return InventoryService.update_product(business_id=user_id, product_id=product_id, data=req)

@router.delete("/products/{product_id}")
def delete_product(
    product_id: str,
    user_id: str = Depends(get_current_user_id),
):
    InventoryService.delete_product(business_id=user_id, product_id=product_id)
    return {"success": True, "deleted_id": product_id}

@router.post("/add-stock", response_model=MovementResponse)
def add_stock(
    req: AddStockRequest,
    user_id: str = Depends(get_current_user_id),
):
    return InventoryService.add_stock(business_id=user_id, req=req)

@router.post("/deduct-sale", response_model=MovementResponse)
def deduct_sale(
    req: DeductSaleRequest,
    user_id: str = Depends(get_current_user_id),
):
    return InventoryService.deduct_stock_sale(business_id=user_id, req=req)

@router.get("/movements", response_model=List[MovementResponse])
def get_movements(
    product_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    return InventoryService.get_movements(business_id=user_id, product_id=product_id, limit=limit)

