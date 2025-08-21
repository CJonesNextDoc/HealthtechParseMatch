# app/db/db_manage.py
import asyncpg
from urllib.parse import urlparse, urlunparse
from app.config import settings

async def ensure_database():
    """
    Connects to the default 'postgres' DB and creates the target DB if missing.
    """
    url = settings.database_url
    # asyncpg can't parse the +asyncpg driver suffix, so strip it
    parsed = urlparse(url.replace("+asyncpg", ""))
    db_name = parsed.path.lstrip("/") or "postgres"

    base = parsed._replace(path="/postgres")
    base_url = urlunparse(base)

    conn = await asyncpg.connect(base_url)
    exists = False
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname=$1", db_name
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            exists = True
    finally:
        await conn.close()

    return exists
