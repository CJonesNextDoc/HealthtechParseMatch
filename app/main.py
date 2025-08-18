from fastapi import FastAPI, Request
import logging
import time
from .config import settings
from .db import check_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FastAPI Demo")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    idem = f"{request.method} {request.url.path}"
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logger.info(f"{idem} completed_in={process_time:.2f}ms status_code={response.status_code}")
    return response

@app.get("/health/check")
async def health_check():
    db_ok = await check_db_connection()
    return {"status": "ok", "db": db_ok}
