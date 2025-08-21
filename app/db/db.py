# app/db/db.py
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.config import settings

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _build_engine():
    kwargs = dict(
        future=True,
        echo=settings.sqlalchemy_echo,
    )
    if settings.testing:
        # test-friendly: no pooling, avoids “another operation is in progress”
        kwargs["poolclass"] = NullPool
        logger.info("In TESTING mode. poolclass = NullPool")
    else:
        # production-friendly pooling (tweak numbers to taste)
        kwargs.update(
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        logger.info("NOT in testing mode. pool_size = 5")
    return create_async_engine(settings.database_url, **kwargs)


def _ensure_sessionmaker():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _build_engine()
        _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _SessionLocal


async def get_db():
    SessionLocal = _ensure_sessionmaker()
    session = SessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def check_db_connection():
    try:
        # ensure engine exists
        _ensure_sessionmaker()
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def create_all():
    _ensure_sessionmaker()
    from app.models.modelbase import Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine():
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
