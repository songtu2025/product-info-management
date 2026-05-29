from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.db import check_database_connection
from app.modules.product_info.routes import router as product_info_router


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(product_info_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name}


@app.get("/db/status")
def db_status():
    return check_database_connection()
