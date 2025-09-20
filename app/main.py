# app/main.py
# ruff: noqa: E402
import uuid

# Add dotenv load & settings cache clear early to ensure Settings picks up .env
from dotenv import load_dotenv

from app.core.config import get_settings

load_dotenv(dotenv_path=".env", override=False)
try:
    get_settings.cache_clear()
except Exception:
    pass

import os
from pathlib import Path
from time import perf_counter
from typing import Callable

import fastapi
from fastapi import APIRouter, FastAPI, Request
from fastapi.concurrency import asynccontextmanager
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.context import request_id_ctx_var
from app.core.middleware import RateLimitMiddleware
from app.db.db import create_all, dispose_engine
from app.db.db_manage import ensure_database
from app.routers import assignments_router, employees_router, health_router, projects_router
from app.routers.dob_router import router as dob_router
from app.routers.patient_router import router as patient_router
from app.routers.zip_router import router as zip_router
from app.utils.logger import get_logger
from app.utils.logging_config import setup_logging

# Configure logging
setup_logging(log_level="INFO")
logger = get_logger(__name__)


async def init_startup():
    # Skip database check in test mode
    if os.getenv("TESTING") == "1":
        logger.info("Test mode - skipping database check")
        return True

    ok = await ensure_database()
    if not ok:
        logger.info("Database not ok, exiting system")
        raise SystemExit(1)
    await create_all()
    logger.info("Database created")


async def shutdown() -> None:
    logger.info("Shutdown hook called — release engine.")
    await dispose_engine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize state
    app.state.rate_limit_cache = {}

    # Database startup
    await init_startup()

    try:
        yield
    finally:
        await shutdown()


app = FastAPI(title="Healthtech Parse+Match API")
router = APIRouter(tags=["FastAPI"])  # Keep this line!

# Move rate limit middleware here - BEFORE logging middleware
logger.info("Registering rate limit middleware")
app.middleware("http")(RateLimitMiddleware())


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable):
    request_id = str(uuid.uuid4())
    token = request_id_ctx_var.set(request_id)

    log_context = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "client_host": request.client.host if request.client else "-",
        "query_params": str(request.query_params),
    }

    try:
        logger.info("Request started", extra=log_context)  # Changed extras to extra
        start_time = perf_counter()

        response = await call_next(request)

        log_context.update(
            {"status_code": response.status_code, "duration_ms": f"{(perf_counter() - start_time) * 1000:.2f}"}
        )
        logger.info("Request completed", extra=log_context)  # Changed extras to extra

        response.headers["X-Request-ID"] = request_id
        return response

    except fastapi.exceptions.HTTPException as http_exc:
        # Handle HTTP exceptions separately to preserve status code
        log_context.update({"status_code": http_exc.status_code, "error": http_exc.detail, "error_type": "HTTPException"})
        logger.info("HTTP exception occurred", extra=log_context)
        raise http_exc  # Re-raise to let FastAPI handle the response

    except Exception as exc:
        log_context.update({"error": str(exc), "error_type": exc.__class__.__name__})
        logger.exception("Request failed", extra=log_context)  # Changed extras to extra
        raise
    finally:
        request_id_ctx_var.reset(token)


# Custom OpenAPI schema generation
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Healthtech Parse+Match API",
        version="0.2.0",
        description="API for parsing and matching healthtech data",
        routes=app.routes,
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "RoleHeader": {"type": "apiKey", "in": "header", "name": "X-Role"},
        "UserEmailHeader": {"type": "apiKey", "in": "header", "name": "X-User-Email"},
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Set the custom OpenAPI schema
app.openapi = custom_openapi

app.include_router(health_router.router)
app.include_router(employees_router.router)
app.include_router(projects_router.router)
app.include_router(assignments_router.router)
app.include_router(dob_router)
app.include_router(zip_router)
app.include_router(patient_router)

# Mount the static directory
static_dir = Path(__file__).resolve().parent.parent.joinpath("app", "static")
# If you prefer a relative path: StaticFiles(directory="app/static")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Serve favicon at the conventional path so browsers find it automatically
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(static_dir.joinpath("favicon.ico"))
