from fastapi import APIRouter, Depends
from app.database import get_current_user_id
from app.models.auth import RegisterRequest, LoginRequest, AuthResponse, BusinessProfile, UpdateBusinessRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api", tags=["Authentication & Business"])

@router.post("/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest):
    return AuthService.register_user(req)

@router.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest):
    return AuthService.login_user(req)

@router.get("/auth/me", response_model=BusinessProfile)
def get_me(user_id: str = Depends(get_current_user_id)):
    return AuthService.get_business_profile(user_id)

@router.get("/business/me", response_model=BusinessProfile)
def get_business(user_id: str = Depends(get_current_user_id)):
    return AuthService.get_business_profile(user_id)

@router.put("/business/me", response_model=BusinessProfile)
def update_business(req: UpdateBusinessRequest, user_id: str = Depends(get_current_user_id)):
    return AuthService.update_business_profile(user_id, req)

