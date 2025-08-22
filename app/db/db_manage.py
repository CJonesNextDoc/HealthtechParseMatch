# app/db/db_manage.py
import asyncpg
import logging
from app.config import settings
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

async def ensure_database():
    """Initialize database connection"""
    if settings.testing:
        # Skip PostgreSQL checks in test mode
        logger.info("Using SQLite for testing")
        return True

    try:
        # Parse the database URL to remove SQLAlchemy-specific parts
        parsed = urlparse(settings.database_url)
        if parsed.scheme.startswith('postgresql+'):
            # Convert postgresql+asyncpg:// to postgresql://
            base_url = settings.database_url.replace('postgresql+asyncpg://', 'postgresql://')
        else:
            base_url = settings.database_url

        logger.info("Checking database connection...")
        conn = await asyncpg.connect(base_url)
        await conn.close()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
