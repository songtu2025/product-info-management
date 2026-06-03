from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.core.db import check_database_connection
from app.core.security import auth_middleware
from app.modules.admin_user.routes import router as admin_user_router
from app.modules.auth.routes import router as auth_router
from app.modules.data_quality.routes import router as data_quality_router
from app.modules.listing_owner.routes import router as listing_owner_router
from app.modules.operation_log.routes import router as operation_log_router
from app.modules.product_import.routes import router as product_import_router
from app.modules.product_info.routes import router as product_info_router
from app.modules.store_site.routes import router as store_site_router


settings = get_settings()
app = FastAPI(title=settings.app_name)
app.middleware("http")(auth_middleware)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth_router)
app.include_router(product_import_router)
app.include_router(product_info_router)
app.include_router(data_quality_router)
app.include_router(store_site_router)
app.include_router(listing_owner_router)
app.include_router(operation_log_router)
app.include_router(admin_user_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name}


@app.get("/db/status")
def db_status():
    return check_database_connection()
