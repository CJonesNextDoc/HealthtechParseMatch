# tests/conftest.py
import os

# 0) Make sure tests run with TESTING=1 before anything imports app.config/settings
os.environ.setdefault("TESTING", "1")

import sys
import asyncio
import logging
import pytest
from httpx import ASGITransport, AsyncClient
from asgi_lifespan import LifespanManager
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
    from app.db.db import create_all, dispose_engine
    await create_all()   # engine will be built with NullPool now
    yield
    await dispose_engine()

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
    return {"X-Role": "manager", "X-User-Email": "tom.smith@emaildomain.com"}

@pytest.fixture
def user_headers_low_clearance():
    return {"X-Role": "user", "X-User-Email": "tom.smith8672121@emaildomain.com"}

@pytest.fixture
def user_headers_mid_clearance():
    return {"X-Role": "user", "X-User-Email": "tom.smith3972274@emaildomain.com"}
