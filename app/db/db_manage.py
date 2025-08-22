# app/db/db_manage.py
import asyncpg
import logging
from app.config import settings

logger = logging.getLogger(__name__)

async def ensure_database():
    """Initialize database connection"""
    if settings.testing:
        # Skip PostgreSQL checks in test mode
        logger.info("Using SQLite for testing")
        return True

    try:
        # Parse the database URL
        base_url = settings.database_url
        logger.info("Checking database connection...")
        conn = await asyncpg.connect(base_url)
        await conn.close()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
