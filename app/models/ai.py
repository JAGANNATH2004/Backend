from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class ProductContext(BaseModel):
    id: str
    name: str
    unit: str
    purchase_price: Optional[float] = 0.0
    selling_price: Optional[float] = 0.0
    current_stock: Optional[float] = 0.0

class VoiceInterpretRequest(BaseModel):
    text: str
    language: str = "te"  # "te" or "en"
    available_products: List[ProductContext] = []

class VoiceInterpretResponse(BaseModel):
    action_type: str  # add_stock, record_sale, check_stock, check_sales, check_reorders, unknown
    product_id: Optional[str] = None
    product_name: str = ""
    quantity: float = 0.0
    unit: str = ""
    unit_price: Optional[float] = None
    expected_stock_balance: Optional[float] = None
    confidence: float = 0.95
    telugu_translation: str = ""
    explanation: str = ""
    raw_speech: str = ""

