import os
import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"🚀 Starting Vyapari AI Backend on http://{settings.HOST}:{settings.PORT}")
    print(f"📖 Swagger OpenAPI documentation: http://localhost:{settings.PORT}/docs")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)

