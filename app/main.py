import uuid
from fastapi import APIRouter, FastAPI, Request
from time import perf_counter
from typing import Callable
import logging
from fastapi.concurrency import asynccontextmanager

from app.db.db import check_db_connection, create_all, dispose_engine
from app.db.db_manage import ensure_database
from app.routers import employees_router, projects_router, assignments_router
from app.utils.logging_config import setup_logging
from app.core.context import request_id_ctx_var

# Configure logging
setup_logging(log_level="INFO")
logger = logging.getLogger(__name__)


async def init_startup():
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
    await init_startup()
    try:
        yield
    finally:
        await shutdown()


app = FastAPI(title="FastAPI Demo", lifespan=lifespan)
router = APIRouter(tags=["FastAPI Demo"])


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

    except Exception as exc:
        log_context.update({
            "error": str(exc),
            "error_type": exc.__class__.__name__
        })
        logger.exception("Request failed", extra=log_context)  # Changed extras to extra
        raise
    finally:
        request_id_ctx_var.reset(token)


@app.get("/health/check")
async def health_check():
    logger.info("Checking db connection")
    db_ok = await check_db_connection()
    return {"status": "ok", "db": db_ok}


app.include_router(employees_router.router)
app.include_router(projects_router.router)
app.include_router(assignments_router.router)
