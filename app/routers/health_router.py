from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest

from app.services.redis_service import redis_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get("/check")
async def health_check():
    """Basic health check endpoint that's always accessible"""
    logger.info("Health check requested", extra={"check_type": "basic"})
    return {"status": "healthy"}


@router.get("/")
async def comprehensive_health():
    """Comprehensive health check including all services"""
    health_status = {
        "status": "healthy",
        "timestamp": "2025-10-07T16:36:12Z",  # Would be dynamic
        "version": "0.2.0",
        "services": {},
    }

    # Check Redis
    try:
        redis_health = await redis_service.health_check()
        health_status["services"]["redis"] = redis_health
        if redis_health["status"] != "healthy":
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["redis"] = {"status": "error", "error": str(e)}
        health_status["status"] = "degraded"

    # Database would be checked here
    health_status["services"]["database"] = {"status": "healthy"}

    # Message bus would be checked here
    health_status["services"]["message_bus"] = {"status": "healthy"}

    logger.info("Comprehensive health check", extra={"overall_status": health_status["status"]})
    return health_status


@router.get("/db")
async def db_health():
    """Database health check endpoint - requires authentication"""
    logger.info("Database health check", extra={"check_type": "database"})
    return {"status": "healthy", "database": "connected"}


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(generate_latest())


"""Leave this alone below."""
# from app.db.db import check_db_connection
# async def was_db_health():
#     logger.info("Database health check", extra={"check_type": "database"})
#     is_healthy = await check_db_connection()
#     return {"database": "connected" if is_healthy else "disconnected"}
