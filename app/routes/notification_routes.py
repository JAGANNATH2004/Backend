from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.database import get_current_user_id, get_supabase

class NotificationResponse(BaseModel):
    id: str
    business_id: str
    product_id: str = None
    title: str
    message: str
    type: str
    is_read: bool = False
    created_at: str

router = APIRouter(prefix="/api/notifications", tags=["Notifications & Alerts"])

@router.get("", response_model=List[NotificationResponse])
def get_notifications(user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    res = supabase.table("notifications").select("*").eq("business_id", user_id).order("created_at", desc=True).limit(50).execute()
    items = []
    for r in (res.data or []):
        items.append(
            NotificationResponse(
                id=str(r["id"]),
                business_id=str(r["business_id"]),
                product_id=str(r["product_id"]) if r.get("product_id") else None,
                title=r.get("title", ""),
                message=r.get("message", ""),
                type=r.get("type", "daily_summary"),
                is_read=bool(r.get("is_read", False)),
                created_at=str(r.get("created_at", "")),
            )
        )
    return items

@router.post("/{notification_id}/read")
def mark_as_read(notification_id: str, user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    supabase.table("notifications").update({"is_read": True}).eq("business_id", user_id).eq("id", notification_id).execute()
    return {"success": True, "read_id": notification_id}

@router.post("/read-all")
def mark_all_as_read(user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    supabase.table("notifications").update({"is_read": True}).eq("business_id", user_id).eq("is_read", False).execute()
    return {"success": True}

