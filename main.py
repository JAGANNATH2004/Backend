from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes.auth_routes import router as auth_router
from app.routes.inventory_routes import router as inventory_router
from app.routes.sales_routes import router as sales_router
from app.routes.dashboard_routes import router as dashboard_router
from app.routes.reports_routes import router as reports_router
from app.routes.notification_routes import router as notification_router
from app.routes.ai_routes import router as ai_router

app = FastAPI(
    title="Vyapari AI Backend API",
    description="Python FastAPI backend powering Telugu voice-first inventory, Supabase database transactions, and Google Gemini Flash-Lite AI.",
    version="1.0.0",
)

# Enable CORS for Flutter mobile, web, and emulator clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(sales_router)
app.include_router(dashboard_router)
app.include_router(reports_router)
app.include_router(notification_router)
app.include_router(ai_router)

@app.get("/")
def root():
    return {
        "service": "Vyapari AI Backend API",
        "status": "online",
        "docs": "/docs",
        "version": "1.0.0",
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY),
        "gemini_configured": bool(settings.GEMINI_API_KEY),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)

