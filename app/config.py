from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",  # load variables from .env
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown env vars
        protected_namespaces=(),
        env_file_exists_ok=True  # Don't error if .env is missing
    )

    # Default to SQLite for testing, otherwise required
    database_url: str = "sqlite+aiosqlite:///./test.db"
    sqlalchemy_echo: bool = False
    testing: bool = False  # can toggle test mode via TESTING=1

settings = Settings()

# Validate settings based on environment
if not settings.testing and settings.database_url == "sqlite+aiosqlite:///./test.db":
    raise ValueError("Production DATABASE_URL must be set")