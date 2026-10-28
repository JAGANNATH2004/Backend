from typing import Optional
from fastapi import HTTPException, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from app.config import settings

_supabase_client: Optional[Client] = None
security = HTTPBearer(auto_error=False)

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            raise HTTPException(
                status_code=500,
                detail="Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in .env",
            )
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _supabase_client

def get_authenticated_supabase(access_token: str) -> Client:
    """Creates a Supabase client configured with the caller's JWT for RLS security."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client

async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """Extracts and validates Supabase JWT token from Authorization header."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication credentials required")
    token = credentials.credentials
    try:
        supabase = get_supabase()
        user_res = supabase.auth.get_user(token)
        if not user_res or not user_res.user:
            raise HTTPException(status_code=401, detail="Invalid or expired authentication token")
        return user_res.user.id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    if not credentials:
        return None
    try:
        supabase = get_supabase()
        user_res = supabase.auth.get_user(credentials.credentials)
        return user_res.user.id if user_res and user_res.user else None
    except Exception:
        return None

