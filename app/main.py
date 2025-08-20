from fastapi import APIRouter, FastAPI, Request, Response
import logging
from time import perf_counter
from fastapi.concurrency import asynccontextmanager

from app.db import check_db_connection, create_all
from app.db_manage import ensure_database
from app.routers import employees_router, projects_router, assignments_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_startup():
    ok = await ensure_database()
    if not ok:
        logger.info("Database not ok, exiting system")
        raise SystemExit(1)
    await create_all()
    logger.info("Database created")


async def shutdown() -> None:
    logger.info("Shutdown hook called — no resources to release yet.")


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
async def log_requests(request: Request, call_next):
    path = request.url.path
    start = perf_counter()
    client = request.client.host if request.client else "-"
    try:
        response: Response = await call_next(request)
        status = response.status_code
        return response
    except Exception as exc:
        status = 500
        logger.exception(f"Unhandled error on {request.method} {path} from {client}. Exception: {exc}")
        raise
    finally:
        elapsed_ms = (perf_counter() - start) * 1000.0
        logger.info(f"{client} {request.method} {path} -> {status} {elapsed_ms}ms")


@app.get("/health/check")
async def health_check():
    logger.info("Checking db connection")
    db_ok = await check_db_connection()
    return {"status": "ok", "db": db_ok}


app.include_router(employees_router.router)
app.include_router(projects_router.router)
app.include_router(assignments_router.router)
