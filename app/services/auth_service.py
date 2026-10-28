from typing import Optional
from fastapi import HTTPException
from app.database import get_supabase
from app.models.auth import RegisterRequest, LoginRequest, AuthResponse, BusinessProfile, UpdateBusinessRequest

class AuthService:
    @staticmethod
    def register_user(req: RegisterRequest) -> AuthResponse:
        supabase = get_supabase()
        try:
            # 1. Sign up with Supabase Auth
            auth_res = supabase.auth.sign_up({
                "email": req.email.strip(),
                "password": req.password,
                "options": {
                    "data": {
                        "shop_name": req.shop_name,
                        "owner_name": req.owner_name,
                    }
                }
            })

            if not auth_res.user:
                raise HTTPException(status_code=400, detail="Registration failed with Supabase Auth")

            user = auth_res.user
            user_id = user.id
            access_token = auth_res.session.access_token if auth_res.session else ""

            # 2. Insert or upsert into businesses table
            business_data = {
                "id": user_id,
                "shop_name": req.shop_name,
                "owner_name": req.owner_name,
                "category": req.category,
                "preferred_language": req.preferred_language if req.preferred_language in ["en", "te"] else "te",
                "phone": req.phone,
            }

            try:
                supabase.table("businesses").upsert(business_data).execute()
            except Exception as e:
                # If businesses table requires auth context or specific insert
                pass

            profile = BusinessProfile(
                id=user_id,
                shop_name=req.shop_name,
                owner_name=req.owner_name,
                category=req.category,
                preferred_language=req.preferred_language,
                phone=req.phone,
            )

            return AuthResponse(
                access_token=access_token,
                user_id=user_id,
                email=req.email,
                business=profile,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def login_user(req: LoginRequest) -> AuthResponse:
        supabase = get_supabase()
        try:
            auth_res = supabase.auth.sign_in_with_password({
                "email": req.email.strip(),
                "password": req.password,
            })

            if not auth_res.user or not auth_res.session:
                raise HTTPException(status_code=401, detail="Invalid email or password")

            user = auth_res.user
            user_id = user.id
            access_token = auth_res.session.access_token

            # Query businesses table
            biz_res = supabase.table("businesses").select("*").eq("id", user_id).execute()
            if biz_res.data and len(biz_res.data) > 0:
                row = biz_res.data[0]
                profile = BusinessProfile(
                    id=user_id,
                    shop_name=row.get("shop_name", "Vyapari Store"),
                    owner_name=row.get("owner_name", "Shopkeeper"),
                    category=row.get("category", "General Store"),
                    preferred_language=row.get("preferred_language", "te"),
                    phone=row.get("phone"),
                    created_at=str(row.get("created_at", "")),
                )
            else:
                # Create profile if not yet created
                metadata = user.user_metadata or {}
                shop_name = metadata.get("shop_name", "Vyapari Store")
                owner_name = metadata.get("owner_name", "Shopkeeper")
                new_biz = {
                    "id": user_id,
                    "shop_name": shop_name,
                    "owner_name": owner_name,
                    "category": "General Store",
                    "preferred_language": "te",
                }
                try:
                    supabase.table("businesses").insert(new_biz).execute()
                except Exception:
                    pass

                profile = BusinessProfile(
                    id=user_id,
                    shop_name=shop_name,
                    owner_name=owner_name,
                    category="General Store",
                    preferred_language="te",
                )

            return AuthResponse(
                access_token=access_token,
                user_id=user_id,
                email=user.email or req.email,
                business=profile,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Login failed: {str(e)}")

    @staticmethod
    def get_business_profile(user_id: str) -> BusinessProfile:
        supabase = get_supabase()
        res = supabase.table("businesses").select("*").eq("id", user_id).execute()
        if res.data and len(res.data) > 0:
            row = res.data[0]
            return BusinessProfile(
                id=user_id,
                shop_name=row.get("shop_name", "Vyapari Store"),
                owner_name=row.get("owner_name", "Shopkeeper"),
                category=row.get("category", "General Store"),
                preferred_language=row.get("preferred_language", "te"),
                phone=row.get("phone"),
                created_at=str(row.get("created_at", "")),
            )
        return BusinessProfile(
            id=user_id,
            shop_name="Vyapari Store",
            owner_name="Shopkeeper",
            category="General Store",
            preferred_language="te",
        )

    @staticmethod
    def update_business_profile(user_id: str, req: UpdateBusinessRequest) -> BusinessProfile:
        supabase = get_supabase()
        update_data = {}
        if req.shop_name is not None:
            update_data["shop_name"] = req.shop_name
        if req.owner_name is not None:
            update_data["owner_name"] = req.owner_name
        if req.category is not None:
            update_data["category"] = req.category
        if req.preferred_language is not None:
            update_data["preferred_language"] = req.preferred_language
        if req.phone is not None:
            update_data["phone"] = req.phone

        if update_data:
            supabase.table("businesses").update(update_data).eq("id", user_id).execute()

        return AuthService.get_business_profile(user_id)

