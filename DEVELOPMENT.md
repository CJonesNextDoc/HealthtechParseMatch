# Development Standards

This document outlines the development standards and patterns used in the HealthtechParseMatch project to ensure consistency, maintainability, and code quality.

## Table of Contents

- [Working with AI Assistants](#working-with-ai-assistants)
- [Async Patterns](#async-patterns)
- [HTTP Client Usage](#http-client-usage)
- [Testing Conventions](#testing-conventions)
- [Code Quality Tools](#code-quality-tools)
- [Pydantic Usage](#pydantic-usage)
- [Database Patterns](#database-patterns)
- [Logging](#logging)
- [Error Handling](#error-handling)
- [Environment Configuration](#environment-configuration)

## Working with AI Assistants

When requesting help from AI coding assistants, use the [REQUEST_TEMPLATE.md](../REQUEST_TEMPLATE.md) to ensure clear, actionable requests that align with project standards.

### Key Principles

- **Be Specific**: Clearly state what you want to achieve
- **Provide Context**: Explain current situation and constraints
- **Reference Standards**: Always mention relevant DEVELOPMENT.md sections
- **Define Success**: Specify acceptance criteria and deliverables

### Template Usage

```markdown
## 🎯 **Goal**
[What you want to achieve - be specific and measurable]

## 📋 **Context**
[Current situation, relevant background, constraints]

## 🔧 **Technical Details**
- **Framework/Tech Stack**: [FastAPI, SQLAlchemy, Redis, etc.]
- **Existing Code**: [Reference specific files/classes/functions]
- **Requirements**: [Functional and non-functional requirements]

## 📝 **Acceptance Criteria**
- [ ] Specific deliverables (files, functions, tests)
- [ ] Code quality standards (async patterns, error handling, etc.)
- [ ] Testing requirements
- [ ] Documentation needs

## 🚫 **Constraints & Preferences**
- [Follow DEVELOPMENT.md standards](#development-standards)
- [Async patterns required](#async-patterns)
- [Testing conventions](#testing-conventions)
```

### Common Mistakes to Avoid

❌ **Vague requests**: "Make it better" or "Add feature X"
❌ **Missing context**: Not explaining current state or constraints
❌ **Ignoring standards**: Not referencing DEVELOPMENT.md patterns
❌ **No acceptance criteria**: Unclear completion requirements

✅ **Clear goals**: Specific, measurable outcomes
✅ **Complete context**: Background and current state
✅ **Technical details**: Files, patterns, requirements specified
✅ **Success criteria**: Deliverables and testing requirements defined

### Quick Checklist

- [ ] **Goal**: Specific and measurable?
- [ ] **Context**: Current situation explained?
- [ ] **Technical Details**: Frameworks and files listed?
- [ ] **Acceptance Criteria**: Clear deliverables defined?
- [ ] **Constraints**: DEVELOPMENT.md standards referenced?

## Async Patterns

### General Rules

- **Always use async/await** for I/O operations
- **Never mix sync and async code** in the same function
- **Use async context managers** for resource management
- **Prefer async generators** for streaming data

### HTTP Clients

```python
# ✅ Good: Use httpx.AsyncClient
async with httpx.AsyncClient(timeout=30) as client:
    response = await client.get(url)
    data = response.json()

# ❌ Bad: Don't use requests in async code
import requests  # Synchronous
response = requests.get(url)  # Blocks event loop
```

### Database Operations

```python
# ✅ Good: Use async SQLAlchemy
async with async_session() as session:
    result = await session.execute(select(User))
    users = result.scalars().all()

# ❌ Bad: Don't use sync SQLAlchemy in async code
with session() as sess:  # Blocks
    users = sess.query(User).all()
```

### Function Signatures

```python
# ✅ Good: Async functions for I/O
async def fetch_user(user_id: int) -> User:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/users/{user_id}")
        return User(**response.json())

# ✅ Good: Sync functions for pure computation
def calculate_age(birth_date: date) -> int:
    return (date.today() - birth_date).days // 365
```

## HTTP Client Usage

### Client Configuration

```python
# ✅ Good: Configure timeouts and limits
client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0, connect=5.0),
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
)

# ❌ Bad: No timeout configuration
client = httpx.AsyncClient()  # Defaults may be too high
```

### Error Handling

```python
# ✅ Good: Handle HTTP errors properly
try:
    response = await client.post(url, json=data)
    response.raise_for_status()
    return response.json()
except httpx.TimeoutException:
    logger.error("Request timed out")
    raise
except httpx.HTTPStatusError as e:
    logger.error(f"HTTP {e.response.status_code}: {e.response.text}")
    raise
```

### Testing HTTP Calls

```python
# ✅ Good: Mock httpx responses
def test_api_call():
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"data": "test"})
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Test your code
```

## Testing Conventions

### Test Structure

```python
# ✅ Good: Use pytest-asyncio for async tests
@pytest.mark.asyncio
async def test_user_creation():
    # Arrange
    user_data = {"name": "John", "email": "john@example.com"}

    # Act
    user = await create_user(user_data)

    # Assert
    assert user.name == "John"
    assert user.email == "john@example.com"
```

### Test Naming

- **Files**: `test_*.py`
- **Functions**: `test_*`
- **Classes**: `Test*`
- **Fixtures**: Descriptive names

### Mocking

```python
# ✅ Good: Use AsyncMock for async functions
mock_function = AsyncMock(return_value="expected_result")

# ✅ Good: Use Mock for sync functions
mock_method = Mock(return_value="sync_result")

# ❌ Bad: Don't mix mock types incorrectly
mock_async = Mock()  # Won't work with await
result = await mock_async()  # TypeError
```

### Fixtures

```python
# ✅ Good: Use async fixtures for database setup
@pytest.fixture
async def db_session():
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.mark.asyncio
async def test_with_db(db_session):
    # Use the session
    pass
```

## Code Quality Tools

### Black (Code Formatting)

- **Line length**: 88 characters
- **Run before commit**: `black .`
- **Configuration**: In `pyproject.toml`

### Ruff (Linting)

- **Replaces**: flake8, isort, pydocstyle
- **Run**: `ruff check .`
- **Fix**: `ruff check . --fix`
- **Configuration**: In `pyproject.toml`

### isort (Import Sorting)

- **Handled by ruff**: No separate configuration needed
- **Import sections**: stdlib, third-party, local
- **Line length**: Matches black

### mypy (Type Checking)

- **Strict mode**: Enabled
- **Run**: `mypy .`
- **Configuration**: In `pyproject.toml`

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: stable
    hooks:
      - id: black

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: stable
    hooks:
      - id: mypy
```

## Pydantic Usage

### Model Definition

```python
# ✅ Good: Use BaseModel for data validation
from pydantic import BaseModel, Field

class User(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ✅ Good: Use ConfigDict for configuration
class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
```

### Validation

```python
# ✅ Good: Let Pydantic handle validation
try:
    user = User(**data)
except ValidationError as e:
    raise HTTPException(status_code=422, detail=e.errors())
```

### Settings

```python
# ✅ Good: Use pydantic-settings for config
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    debug: bool = False
    api_key: str = Field(..., env="API_KEY")

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
```

## Database Patterns

### Session Management

```python
# ✅ Good: Use async session context
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user(db: AsyncSession, user_id: int):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

### Model Definition

```python
# ✅ Good: Use SQLAlchemy 2.0 style
from sqlalchemy.orm import Mapped, mapped_column

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
```

### Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "Add user table"

# Run migration
alembic upgrade head
```

## Logging

### Configuration

```python
# ✅ Good: Use structured logging
import logging
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)

# Configure for production
handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```

### Usage

```python
# ✅ Good: Include context in logs
logger.info("User created", extra={
    "user_id": user.id,
    "email": user.email,
    "timestamp": user.created_at.isoformat()
})

# ✅ Good: Log errors with stack traces
try:
    await risky_operation()
except Exception as e:
    logger.error("Operation failed", exc_info=True, extra={"operation": "risky_operation"})
```

## Error Handling

### Custom Exceptions

```python
# ✅ Good: Define domain-specific exceptions
class UserNotFoundError(ValueError):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")

class ValidationError(ValueError):
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")
```

### API Error Responses

```python
# ✅ Good: Consistent error responses
from fastapi import HTTPException

@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "User not found", "user_id": exc.user_id}
    )

# ✅ Good: Use HTTPException for standard errors
raise HTTPException(status_code=400, detail="Invalid input")
```

## Environment Configuration

### .env File Structure

```bash
# .env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-here
DEBUG=false
```

### Settings Management

```python
# ✅ Good: Centralize configuration
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = Field(..., env="DATABASE_URL")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")

    # Security
    secret_key: str = Field(..., env="SECRET_KEY", min_length=32)
    algorithm: str = "HS256"

    # App settings
    debug: bool = Field(default=False, env="DEBUG")

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
```

### Validation

```python
# ✅ Good: Validate at startup
@app.on_event("startup")
async def validate_settings():
    # Test database connection
    try:
        async with create_async_engine(settings.database_url).connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Database connection failed", exc_info=True)
        raise

    logger.info("Settings validated successfully")
```

---

## Quick Reference

### Running Quality Checks

```bash
# Format code
black .

# Lint and fix
ruff check . --fix

# Type check
mypy .

# Run tests
pytest

# All together (with pre-commit)
pre-commit run --all-files
```

### Common Patterns

- **HTTP**: `httpx.AsyncClient` with timeouts
- **DB**: Async SQLAlchemy with context managers
- **Config**: Pydantic settings with validation
- **Testing**: pytest-asyncio with proper mocking
- **Logging**: Structured logging with context

Remember: Code is read more than it's written. Prioritize clarity and consistency over cleverness.</content>
<parameter name="filePath">c:\repo\HealthtechParseMatch\DEVELOPMENT.md
