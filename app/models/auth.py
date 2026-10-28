from typing import Optional
from pydantic import BaseModel, Field

class BusinessProfile(BaseModel):
    id: str
    shop_name: str
    owner_name: str
    category: str = "General Store"
    preferred_language: str = "te"
    phone: Optional[str] = None
    created_at: Optional[str] = None

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    shop_name: str = "Vyapari Store"
    owner_name: str = "Shopkeeper"
    category: str = "General Store"
    preferred_language: str = "te"
    phone: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    business: BusinessProfile

class UpdateBusinessRequest(BaseModel):
    shop_name: Optional[str] = None
    owner_name: Optional[str] = None
    category: Optional[str] = None
    preferred_language: Optional[str] = None
    phone: Optional[str] = None

