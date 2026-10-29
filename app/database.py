from typing import Optional
import jwt
from fastapi import HTTPException, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from app.config import settings

_supabase_client: Optional[Client] = None
_supabase_admin_client: Optional[Client] = None
security = HTTPBearer(auto_error=False)

def get_supabase(token: Optional[str] = None) -> Client:
    """
    Returns a Supabase client.
    Prefers SUPABASE_SERVICE_ROLE_KEY to bypass Row Level Security on the backend server.
    If service role key is not configured, attaches user token if available.
    """
    global _supabase_client, _supabase_admin_client

    # 1. Server-side admin client (bypasses RLS)
    if settings.SUPABASE_SERVICE_ROLE_KEY:
        if _supabase_admin_client is None:
            _supabase_admin_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        return _supabase_admin_client

    # 2. Token-authenticated client for RLS
    if token:
        return get_authenticated_supabase(token)

    # 3. Default anon client
    if _supabase_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            raise HTTPException(
                status_code=500,
                detail="Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in .env",
            )
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _supabase_client

def get_supabase_admin() -> Client:
    """Returns the administrative Supabase client using SUPABASE_SERVICE_ROLE_KEY if set."""
    if settings.SUPABASE_SERVICE_ROLE_KEY:
        global _supabase_admin_client
        if _supabase_admin_client is None:
            _supabase_admin_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        return _supabase_admin_client
    return get_supabase()

def get_authenticated_supabase(access_token: str) -> Client:
    """Creates a Supabase client configured with the caller's JWT for RLS security."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client

async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> str:
    """Extracts and validates JWT token from Authorization header."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication credentials required. Please log in.")
    token = credentials.credentials

    # 1. First attempt to decode using our application JWT secret (from users table auth)
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("user_id") or payload.get("sub")
        if user_id:
            return str(user_id)
    except Exception:
        pass

    # 2. Fallback to Supabase Auth token verification
    try:
        supabase = get_supabase()
        user_res = supabase.auth.get_user(token)
        if user_res and user_res.user:
            return user_res.user.id
    except Exception:
        pass

    raise HTTPException(status_code=401, detail="Invalid or expired authentication token. Please log in again.")

async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    if not credentials or not credentials.credentials:
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("user_id") or payload.get("sub")
        if user_id:
            return str(user_id)
    except Exception:
        pass

    try:
        supabase = get_supabase()
        user_res = supabase.auth.get_user(token)
        return user_res.user.id if user_res and user_res.user else None
    except Exception:
        return None

