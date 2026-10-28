from typing import Optional
from pydantic import BaseModel, Field

class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = ""
    category: str = "General Store"
    unit: str = "Packets"
    current_stock: float = Field(default=0.0, ge=0)
    purchase_price: float = Field(default=0.0, ge=0)
    selling_price: float = Field(ge=0)
    min_threshold: float = Field(default=10.0, ge=0)
    supplier: Optional[str] = ""

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    current_stock: Optional[float] = None
    purchase_price: Optional[float] = None
    selling_price: Optional[float] = None
    min_threshold: Optional[float] = None
    supplier: Optional[str] = None

class ProductResponse(BaseModel):
    id: str
    name: str
    sku: str = ""
    category: str = "General Store"
    unit: str = "Packets"
    current_stock: float
    purchase_price: float
    selling_price: float
    min_threshold: float = 10.0
    supplier: str = ""
    status: str = "inStock"
    updated_at: Optional[str] = None

class AddStockRequest(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    purchase_price: float = Field(ge=0)
    supplier: Optional[str] = ""
    notes: Optional[str] = ""

class DeductSaleRequest(BaseModel):
    product_id: str
    quantity: float = Field(gt=0)
    selling_price: float = Field(ge=0)
    notes: Optional[str] = ""

class MovementResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    type: str  # purchase, sale, adjustment
    quantity: float
    unit: str
    price: float
    previous_stock: float
    new_stock: float
    timestamp: str
    notes: Optional[str] = ""

