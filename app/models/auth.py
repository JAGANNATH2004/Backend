from typing import Optional
from pydantic import BaseModel, Field

class BusinessProfile(BaseModel):
    id: str
    shop_name: str
    owner_name: str
    category: str = "General Store"
    preferred_language: str = "en"
    phone: Optional[str] = None
    email_id: Optional[str] = None
    created_at: Optional[str] = None

class RegisterRequest(BaseModel):
    mobile_no: Optional[str] = None
    user_name: Optional[str] = None
    password: str = Field(min_length=6)
    shop_name: str = "Vyapari Store"
    owner_name: Optional[str] = "Shopkeeper"
    category: str = "General Store"
    preferred_language: str = "en"
    phone: Optional[str] = None
    email: Optional[str] = None
    email_id: Optional[str] = None

class LoginRequest(BaseModel):
    mobile_no: Optional[str] = None
    email: Optional[str] = None
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    mobile_no: Optional[str] = None
    user_name: Optional[str] = None
    shop_name: Optional[str] = None
    email: Optional[str] = None
    email_id: Optional[str] = None
    business: BusinessProfile

class UpdateBusinessRequest(BaseModel):
    shop_name: Optional[str] = None
    owner_name: Optional[str] = None
    category: Optional[str] = None
    preferred_language: Optional[str] = None
    phone: Optional[str] = None
    email_id: Optional[str] = None

class UpdateUserProfileRequest(BaseModel):
    user_name: Optional[str] = None
    mobile_no: Optional[str] = None
    email_id: Optional[str] = None
    password: Optional[str] = None
    shop_name: Optional[str] = None
    category: Optional[str] = None
    preferred_language: Optional[str] = None

