import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import HTTPException
from app.database import get_supabase, get_supabase_admin, get_authenticated_supabase
from app.config import settings
from app.models.auth import RegisterRequest, LoginRequest, AuthResponse, BusinessProfile, UpdateBusinessRequest

class AuthService:
    @staticmethod
    def _clean_mobile(val: Optional[str]) -> str:
        if not val:
            return ""
        val = val.strip()
        if "@" in val:
            val = val.split("@")[0]
        cleaned = re.sub(r"[^0-9a-zA-Z+]", "", val)
        return cleaned

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return f"pbkdf2:{salt}:{key.hex()}"

    @staticmethod
    def _verify_password(plain_password: str, hashed_password: str) -> bool:
        if not hashed_password or not plain_password:
            return False
        try:
            if hashed_password.startswith("pbkdf2:"):
                parts = hashed_password.split(":")
                salt = parts[1]
                expected_hex = parts[2]
                key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
                return secrets.compare_digest(key.hex(), expected_hex)
            if hashed_password == plain_password:
                return True
            if hashlib.sha256(plain_password.encode("utf-8")).hexdigest() == hashed_password:
                return True
        except Exception:
            return False
        return False

    @staticmethod
    def _create_token(user_id: str, mobile_no: str, user_name: str, shop_name: str) -> str:
        payload = {
            "user_id": user_id,
            "sub": user_id,
            "mobile_no": mobile_no,
            "user_name": user_name,
            "shop_name": shop_name,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRATION_DAYS),
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def register_user(req: RegisterRequest) -> AuthResponse:
        db = get_supabase_admin()

        raw_mobile = req.mobile_no or req.phone or req.email
        mobile_no = AuthService._clean_mobile(raw_mobile)
        if not mobile_no:
            raise HTTPException(status_code=400, detail="Mobile Number is required for registration.")

        user_name = (req.user_name or req.owner_name or "Shopkeeper").strip()
        shop_name = (req.shop_name or "Vyapari Store").strip()
        category = req.category or "General Store"
        preferred_language = req.preferred_language if req.preferred_language in ["en", "te"] else "te"

        # 1. Check if user already exists with this mobile number in public.users
        try:
            existing = db.table("users").select("id, mobile_no").eq("mobile_no", mobile_no).execute()
            if existing.data and len(existing.data) > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"A user with Mobile Number '{mobile_no}' already exists. Please log in instead.",
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"Check existing user notice: {e}")

        # 2. Generate unique user_id and securely hash password
        user_id = str(uuid.uuid4())
        hashed_password = AuthService._hash_password(req.password)

        # 3. Store user in database table: (Mobile No, User Name, Password, Shop Name)
        user_row = {
            "id": user_id,
            "mobile_no": mobile_no,
            "user_name": user_name,
            "password_hash": hashed_password,
            "shop_name": shop_name,
            "category": category,
            "preferred_language": preferred_language,
        }

        try:
            db.table("users").insert(user_row).execute()
        except Exception as e:
            try:
                get_supabase().table("users").insert(user_row).execute()
            except Exception as e2:
                print(f"Error saving to users table: {e2}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to save user in 'users' table. Please run the SQL schema in Supabase SQL Editor. Error: {str(e2)}",
                )

        # 4. Synchronize with businesses table (so all foreign key links for products/sales work)
        biz_data = {
            "id": user_id,
            "shop_name": shop_name,
            "owner_name": user_name,
            "category": category,
            "preferred_language": preferred_language,
            "phone": mobile_no,
        }
        try:
            db.table("businesses").upsert(biz_data).execute()
        except Exception as e:
            try:
                get_supabase().table("businesses").upsert(biz_data).execute()
            except Exception:
                pass

        # 5. Create authentication token
        token = AuthService._create_token(user_id, mobile_no, user_name, shop_name)

        profile = BusinessProfile(
            id=user_id,
            shop_name=shop_name,
            owner_name=user_name,
            category=category,
            preferred_language=preferred_language,
            phone=mobile_no,
        )

        return AuthResponse(
            access_token=token,
            user_id=user_id,
            mobile_no=mobile_no,
            user_name=user_name,
            shop_name=shop_name,
            email=f"{mobile_no}@vyapari.ai",
            business=profile,
        )

    @staticmethod
    def login_user(req: LoginRequest) -> AuthResponse:
        db = get_supabase_admin()
        raw_identifier = req.mobile_no or req.email
        clean_mobile = AuthService._clean_mobile(raw_identifier)

        if not clean_mobile and not raw_identifier:
            raise HTTPException(status_code=400, detail="Mobile Number or Username is required.")

        user_record = None

        # 1. Query public.users table by Mobile No (or User Name)
        try:
            res = db.table("users").select("*").eq("mobile_no", clean_mobile).execute()
            if res.data and len(res.data) > 0:
                user_record = res.data[0]
            elif raw_identifier:
                res2 = db.table("users").select("*").eq("user_name", raw_identifier.strip()).execute()
                if res2.data and len(res2.data) > 0:
                    user_record = res2.data[0]
        except Exception:
            try:
                res = get_supabase().table("users").select("*").eq("mobile_no", clean_mobile).execute()
                if res.data and len(res.data) > 0:
                    user_record = res.data[0]
            except Exception:
                pass

        # 2. Check password against password_hash stored in the database
        if user_record:
            stored_hash = user_record.get("password_hash") or ""
            if not AuthService._verify_password(req.password, stored_hash):
                raise HTTPException(status_code=401, detail="Invalid Mobile Number or Password")

            user_id = str(user_record["id"])
            mobile_no = user_record.get("mobile_no", clean_mobile)
            user_name = user_record.get("user_name", "Shopkeeper")
            shop_name = user_record.get("shop_name", "Vyapari Store")
            category = user_record.get("category", "General Store")
            preferred_language = user_record.get("preferred_language", "te")

            # Ensure businesses row is synchronized
            biz_data = {
                "id": user_id,
                "shop_name": shop_name,
                "owner_name": user_name,
                "category": category,
                "preferred_language": preferred_language,
                "phone": mobile_no,
            }
            try:
                db.table("businesses").upsert(biz_data).execute()
            except Exception:
                pass

            token = AuthService._create_token(user_id, mobile_no, user_name, shop_name)
            profile = BusinessProfile(
                id=user_id,
                shop_name=shop_name,
                owner_name=user_name,
                category=category,
                preferred_language=preferred_language,
                phone=mobile_no,
                created_at=str(user_record.get("created_at", "")),
            )

            return AuthResponse(
                access_token=token,
                user_id=user_id,
                mobile_no=mobile_no,
                user_name=user_name,
                shop_name=shop_name,
                email=f"{mobile_no}@vyapari.ai",
                business=profile,
            )

        # 3. Fallback: Check Supabase Auth for legacy users
        try:
            supabase = get_supabase()
            email_to_try = req.email.strip() if req.email else f"{clean_mobile}@vyapari.ai"
            auth_res = supabase.auth.sign_in_with_password({
                "email": email_to_try,
                "password": req.password,
            })
            if auth_res.user and auth_res.session:
                user = auth_res.user
                user_id = user.id
                access_token = auth_res.session.access_token
                meta = user.user_metadata or {}
                shop_name = meta.get("shop_name", "Vyapari Store")
                owner_name = meta.get("owner_name", "Shopkeeper")

                # Auto-migrate into public.users table
                new_user_row = {
                    "id": user_id,
                    "mobile_no": clean_mobile or user_id[:10],
                    "user_name": owner_name,
                    "password_hash": AuthService._hash_password(req.password),
                    "shop_name": shop_name,
                    "category": "General Store",
                    "preferred_language": "te",
                }
                try:
                    db.table("users").upsert(new_user_row).execute()
                except Exception:
                    pass

                profile = AuthService.get_business_profile(user_id)
                return AuthResponse(
                    access_token=access_token,
                    user_id=user_id,
                    mobile_no=clean_mobile,
                    user_name=owner_name,
                    shop_name=shop_name,
                    email=user.email or email_to_try,
                    business=profile,
                )
        except Exception:
            pass

        raise HTTPException(status_code=401, detail="Invalid Mobile Number or Password")

    @staticmethod
    def get_business_profile(user_id: str) -> BusinessProfile:
        db = get_supabase_admin()
        try:
            res = db.table("businesses").select("*").eq("id", user_id).execute()
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
        except Exception as e:
            print(f"Warning: Failed to fetch business profile: {e}")

        return BusinessProfile(
            id=user_id,
            shop_name="Vyapari Store",
            owner_name="Shopkeeper",
            category="General Store",
            preferred_language="te",
        )

    @staticmethod
    def update_business_profile(user_id: str, req: UpdateBusinessRequest) -> BusinessProfile:
        db = get_supabase_admin()
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
            try:
                db.table("businesses").update(update_data).eq("id", user_id).execute()
            except Exception as e:
                print(f"Warning: Failed to update business profile: {e}")

        return AuthService.get_business_profile(user_id)

