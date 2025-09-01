# app/db/test_db.py
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Use the async SQLite driver for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create a single async engine for the test DB
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,  # keep SA 2.x behavior explicit for typing
)

# Async session factory (typed)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # explicit; adjust if you prefer True
)

__all__ = [
    "TEST_DATABASE_URL",
    "test_engine",
    "TestingSessionLocal",
]
