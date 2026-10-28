from typing import List, Optional
from pydantic import BaseModel, Field

class SaleItemRequest(BaseModel):
    product_id: str
    product_name: str
    quantity: float = Field(gt=0)
    unit: str
    unit_price: float = Field(ge=0)

class RecordSaleRequest(BaseModel):
    items: List[SaleItemRequest] = Field(min_length=1)
    discount: float = Field(default=0.0, ge=0)
    notes: Optional[str] = ""

class SaleItemResponse(BaseModel):
    product_id: str
    product_name: str
    quantity: float
    unit: str
    unit_price: float
    subtotal: float

class SaleResponse(BaseModel):
    id: str
    receipt_number: str
    items: List[SaleItemResponse]
    subtotal: float
    discount: float
    total_amount: float
    timestamp: str
    notes: Optional[str] = ""

