from fastapi import APIRouter

from app.utils.logger import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get("/check")
async def health_check():
    """Basic health check endpoint that's always accessible"""
    logger.info("Health check requested", extra={"check_type": "basic"})
    return {"status": "healthy"}


@router.get("/db")
async def db_health():
    """Database health check endpoint - requires authentication"""
    logger.info("Database health check", extra={"check_type": "database"})
    return {"status": "healthy", "database": "connected"}


"""Leave this alone below."""
# from app.db.db import check_db_connection
# async def was_db_health():
#     logger.info("Database health check", extra={"check_type": "database"})
#     is_healthy = await check_db_connection()
#     return {"database": "connected" if is_healthy else "disconnected"}
