# app/db/db_manage.py
import asyncpg
# from urllib.parse import urlparse
from logging import getLogger
import os
from dotenv import load_dotenv

from app.core.config import get_settings

logger = getLogger(__name__)


def ensure_settings_from_env() -> None:
    """
    Load .env into the environment and force a fresh Settings instance.

    This avoids importing settings at module import time which would lock in
    the default database_url before .env is read.
    """
    # Load .env (if present) into os.environ so pydantic Settings picks it up
    load_dotenv(dotenv_path=".env", override=False)

    # Clear the cached Settings factory so get_settings() rebuilds using the env
    try:
        get_settings.cache_clear()
    except AttributeError:
        # If get_settings isn't cached, ignore
        pass


def get_database_url() -> str:
    """
    Ensure settings are constructed after .env is loaded and return the
    effective database_url. Raises ValueError if running non-testing and
    no production DATABASE_URL is configured (preserves previous behavior).
    """
    ensure_settings_from_env()
    settings = get_settings()
    # validate_db_url will raise if production DB url is missing
    settings.validate_db_url()
    return settings.database_url


async def ensure_database():
    """Verify database connection"""
    # Ensure .env is loaded and settings built from it
    ensure_settings_from_env()
    settings = get_settings()

    logger.info(f"Effective TESTING flag: {settings.is_testing}")
    logger.info(f"TESTING in env: {os.getenv("TESTING")}")
    if os.getenv("TESTING") == "1":
        logger.info("Test mode - using SQLite")
        return True

    # Log raw repr so we can detect stray whitespace or bad chars
    db_url_raw = getattr(settings, "database_url", "") or ""
    db_url = db_url_raw.strip()
    if db_url != db_url_raw:
        logger.warning("DATABASE_URL contained surrounding whitespace; using stripped value")

    logger.info("Checking database connection...")
    try:
        # Convert async driver scheme to one asyncpg accepts
        if db_url.startswith("postgresql+"):
            base_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        else:
            base_url = db_url

        conn = await asyncpg.connect(dsn=base_url)
        await conn.close()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False


def main() -> None:
    """Simple CLI entry to print the configured database URL (or error)."""
    db_url = get_database_url()
    print(f"Using database URL: {db_url}")


if __name__ == "__main__":
    main()
