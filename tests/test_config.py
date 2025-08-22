from sqlalchemy.ext.asyncio import create_async_engine

# Use SQLite URL for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create async engine with SQLite-specific connect args
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)