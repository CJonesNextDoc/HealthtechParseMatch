import uuid
# Add dotenv load & settings cache clear early to ensure Settings picks up .env
from dotenv import load_dotenv
from app.core.config import get_settings
load_dotenv(dotenv_path=".env", override=False)
try:
    get_settings.cache_clear()
except Exception:
    pass

from fastapi import APIRouter, FastAPI, Request  # noqa: E402
from time import perf_counter  # noqa: E402
from typing import Callable  # noqa: E402
import logging  # noqa: E402
import fastapi  # noqa: E402
from fastapi.concurrency import asynccontextmanager  # noqa: E402
from fastapi.openapi.utils import get_openapi  # noqa: E402
import os  # noqa: E402

from app.db.db import create_all, dispose_engine  # noqa: E402
from app.db.db_manage import ensure_database  # noqa: E402
from app.routers import employees_router, projects_router, assignments_router, health_router  # noqa: E402
from app.utils.logging_config import setup_logging  # noqa: E402
from app.core.context import request_id_ctx_var  # noqa: E402
from app.core.middleware import RateLimitMiddleware  # noqa: E402

# Configure logging
setup_logging(log_level="INFO")
logger = logging.getLogger(__name__)


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


app = FastAPI(title="FastAPI Demo", lifespan=lifespan)
router = APIRouter(tags=["FastAPI Demo"])  # Keep this line!

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
        "query_params": str(request.query_params)
    }

    try:
        logger.info("Request started", extra=log_context)  # Changed extras to extra
        start_time = perf_counter()
        
        response = await call_next(request)
        
        log_context.update({
            "status_code": response.status_code,
            "duration_ms": f"{(perf_counter() - start_time) * 1000:.2f}"
        })
        logger.info("Request completed", extra=log_context)  # Changed extras to extra
        
        response.headers["X-Request-ID"] = request_id
        return response
    
    except fastapi.exceptions.HTTPException as http_exc:
        # Handle HTTP exceptions separately to preserve status code
        log_context.update({
            "status_code": http_exc.status_code,
            "error": http_exc.detail,
            "error_type": "HTTPException"
        })
        logger.info("HTTP exception occurred", extra=log_context)
        raise http_exc  # Re-raise to let FastAPI handle the response

    except Exception as exc:
        log_context.update({
            "error": str(exc),
            "error_type": exc.__class__.__name__
        })
        logger.exception("Request failed", extra=log_context)  # Changed extras to extra
        raise
    finally:
        request_id_ctx_var.reset(token)


# Custom OpenAPI schema generation
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="FastAPI Scaffold Demo",
        version="0.2.0",
        description="A scaffolding template for FastAPI applications with RBAC and structured logging",
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "RoleHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Role"
        },
        "UserEmailHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-User-Email"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Set the custom OpenAPI schema
app.openapi = custom_openapi

app.include_router(health_router.router)
app.include_router(employees_router.router)
app.include_router(projects_router.router)
app.include_router(assignments_router.router)
