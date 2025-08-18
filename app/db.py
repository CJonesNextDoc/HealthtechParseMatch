from sqlalchemy.ext.asyncio import create_async_engine
from .config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)

async def check_db_connection():
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception:
        return False
