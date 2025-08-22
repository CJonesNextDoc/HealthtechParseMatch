# tests/conftest.py
import os
import sys
import pytest
import logging
import asyncio

# Set test environment variables BEFORE any app imports
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["SQLALCHEMY_ECHO"] = "false"

# Now we can safely import app components
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager
from sqlalchemy import text
from app.main import app

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
    return {"X-Role": "user", "X-User-Email": "john.doe@example.com"}

@pytest.fixture
def user_headers_mid_clearance():
    return {"X-Role": "user", "X-User-Email": "tom.smith@example.com"}

@pytest.fixture(autouse=True)
async def setup_test_data():
    """Create initial test data"""
    from app.models.employee import Employee
    from app.db.test_db import TestingSessionLocal
    from sqlalchemy import text
    
    async with TestingSessionLocal() as session:
        # Clear any existing data
        await session.execute(text("DELETE FROM employee"))
        
        # Create initial employee record
        employee = Employee(
            email="curtisjonesknox@gmail.com",
            full_name="Curtis Jones",
            clearance_level=5
        )
        session.add(employee)
        
        # Create initial employee record
        employee2 = Employee(
            email="tom.smith@example.com",
            full_name="Tom Smith",
            clearance_level=3
        )
        session.add(employee2)
        
        # Create initial employee record
        employee3 = Employee(
            email="john.doe@example.com",
            full_name="John Doe",
            clearance_level=1
        )
        session.add(employee3)

        await session.commit()
    
    yield


@pytest.fixture(autouse=True)
async def setup_project_test_data():
    """Create initial project test data"""
    from app.models.project import Project
    from app.db.test_db import TestingSessionLocal
    
    async with TestingSessionLocal() as session:
        # Clear existing data
        await session.execute(text("DELETE FROM project"))
        await session.commit()
        
        # Create initial projects with explicit IDs for testing
        projects = [
            Project(
                id=1,  # Explicit ID for first record
                code="PRJ-RED",
                title="Red Hawk",
                min_clearance=3
            ),
            Project(
                id=2,  # Explicit ID for second record
                code="PRJ-BLUE",
                title="Blue Heron",
                min_clearance=1
            )
        ]
        for project in projects:
            session.add(project)
        await session.commit()
    
    yield

@pytest.fixture(autouse=True)
async def setup_assignment_test_data():
    """Create initial assignment test data"""
    from app.models.assignment import Assignment
    from app.db.test_db import TestingSessionLocal
    from sqlalchemy import text

    async with TestingSessionLocal() as session:
        # Clear existing assignments
        await session.execute(text("DELETE FROM assignment"))
        await session.commit()

        # Create initial assignments
        assignments = [
            Assignment(
                id=1,
                employee_id=1,
                project_id=1,
                role="lead"
            ),
            Assignment(
                id=2,
                employee_id=2,
                project_id=2,
                role="member"
            )
        ]
        for assignment in assignments:
            session.add(assignment)
        await session.commit()

    yield
