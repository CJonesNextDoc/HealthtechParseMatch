# tests/conftest.py
import os
import sys

import pytest
from httpx import AsyncClient

from app.core.middleware import RateLimiter
from app.main import app

# Set test environment variables BEFORE any app imports
os.environ["TESTING"] = "1"
os.environ["RATE_LIMIT_TEST"] = "1"  # Enable rate limiting in tests
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["SQLALCHEMY_ECHO"] = "false"
os.environ["USER_RATE_LIMIT"] = "2"  # Only allow 2 requests per second for users
os.environ["MANAGER_RATE_LIMIT"] = "5"  # 5 requests per second for managers
os.environ["ADMIN_RATE_LIMIT"] = "10"  # 10 requests per second for admins
os.environ["APP_RATE_LIMIT"] = "20"  # 20 requests per second for vendor apps

# Now we can safely import app components
import asyncio
import logging

from asgi_lifespan import LifespanManager
from httpx import ASGITransport
from sqlalchemy import text

# 1) Windows: force Selector loop (asyncpg + Proactor)
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# 2) Force anyio to use asyncio
@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


# 3) Show INFO logs during pytest
@pytest.fixture(scope="session", autouse=True)
def _configure_log_cli():
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.INFO)
    else:
        root.setLevel(logging.INFO)


# 4) Create tables once, dispose engine once
@pytest.fixture(scope="session", autouse=True)
async def _db_schema_and_cleanup():
    """Create and clean up test database"""
    import atexit
    import os

    from app.db.test_db import test_engine
    from app.models.modelbase import Base

    # Drop and recreate all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Cleanup
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

    # Register cleanup at process exit
    def cleanup_db():
        try:
            if os.path.exists("./test.db"):
                os.remove("./test.db")
        except PermissionError:
            pass  # Ignore if file is locked

    atexit.register(cleanup_db)


@pytest.fixture
async def client():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)  # no lifespan kwarg on httpx 0.28+
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
def manager_headers():
    return {"X-Role": "manager", "X-User-Email": "curtisjonesknox@gmail.com"}


@pytest.fixture
def vendor_headers():
    return {"X-Role": "vendor_app", "X-User-Email": "curtisjonesknox@gmail.com"}


@pytest.fixture
def admin_headers():
    return {"X-Role": "admin", "X-User-Email": "curtisjonesknox@gmail.com"}


@pytest.fixture
def manager_headers_low_clearance():
    return {"X-Role": "manager", "X-User-Email": "john.doe@example.com"}


@pytest.fixture
def user_headers_low_clearance():
    """Headers for a regular user"""
    return {"X-Role": "user", "X-User-Email": "john.doe@example.com"}


@pytest.fixture
def user_headers_mid_clearance():
    return {"X-Role": "user", "X-User-Email": "tom.smith@example.com"}


@pytest.fixture(autouse=True)
async def setup_test_data():
    """Create initial test data"""
    from sqlalchemy import text

    from app.db.test_db import TestingSessionLocal
    from app.models.employee import Employee

    async with TestingSessionLocal() as session:
        # Clear any existing data
        await session.execute(text("DELETE FROM employee"))

        # Create initial employee record
        employee = Employee(email="curtisjonesknox@gmail.com", full_name="Curtis Jones", clearance_level=5)
        session.add(employee)

        # Create initial employee record
        employee2 = Employee(email="tom.smith@example.com", full_name="Tom Smith", clearance_level=3)
        session.add(employee2)

        # Create initial employee record
        employee3 = Employee(email="john.doe@example.com", full_name="John Doe", clearance_level=1)
        session.add(employee3)

        await session.commit()

    yield


@pytest.fixture(autouse=True)
async def setup_project_test_data():
    """Create initial project test data"""
    from app.db.test_db import TestingSessionLocal
    from app.models.project import Project

    async with TestingSessionLocal() as session:
        # Clear existing data
        await session.execute(text("DELETE FROM project"))
        await session.commit()

        # Create initial projects with explicit IDs for testing
        projects = [
            Project(id=1, code="PRJ-RED", title="Red Hawk", min_clearance=3),  # Explicit ID for first record
            Project(id=2, code="PRJ-BLUE", title="Blue Heron", min_clearance=1),  # Explicit ID for second record
        ]
        for project in projects:
            session.add(project)
        await session.commit()

    yield


@pytest.fixture(autouse=True)
async def setup_assignment_test_data(_db_schema_and_cleanup):
    """Setup test data for assignments"""
    from sqlalchemy import text

    from app.db.test_db import TestingSessionLocal, test_engine
    from app.models.assignment import Assignment
    from app.models.modelbase import Base

    # Ensure tables exist
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        # Now safe to delete
        await session.execute(text("DELETE FROM assignment"))

        # Create initial assignments
        assignments = [
            Assignment(id=1, employee_id=1, project_id=1, role="lead"),
            Assignment(id=2, employee_id=2, project_id=2, role="member"),
        ]
        for assignment in assignments:
            session.add(assignment)
        await session.commit()

    yield


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Configure logging for tests"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add file handler
    file_handler = logging.FileHandler("test_output.txt", mode="w", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    yield

    # Clean up handlers
    logger.removeHandler(file_handler)
    logger.removeHandler(console_handler)
    file_handler.close()


@pytest.fixture(autouse=True)
def verify_rate_limit_settings():
    """Verify rate limit environment variables are set correctly"""
    assert os.getenv("RATE_LIMIT_TEST") == "1"
    assert os.getenv("RATE_LIMIT_WINDOW") == "1"
    assert os.getenv("USER_RATE_LIMIT") == "2"
    assert os.getenv("MANAGER_RATE_LIMIT") == "5"
    assert os.getenv("ADMIN_RATE_LIMIT") == "10"
    assert os.getenv("APP_RATE_LIMIT") == "20"
    yield


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables"""
    from app.core.config import get_settings

    # Clear settings cache
    get_settings.cache_clear()

    # Set test environment variables
    os.environ["TESTING"] = "1"
    os.environ["RATE_LIMIT_TEST"] = "1"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
    os.environ["USER_RATE_LIMIT"] = "2"  # 2 requests per second for tests
    os.environ["RATE_LIMIT_WINDOW"] = "1"  # 1 second window

    # Verify settings are correct
    settings = get_settings()
    assert settings.rate_limit_test is True
    assert settings.user_rate_limit == 2
    assert settings.rate_limit_window == 1

    yield

    # Clean up
    os.environ.pop("TESTING", None)
    os.environ.pop("RATE_LIMIT_TEST", None)
    get_settings.cache_clear()  # Clear cache again after test


@pytest.fixture
def rate_limiter():
    """Create a fresh RateLimiter instance for tests."""
    return RateLimiter()
