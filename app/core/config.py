from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application settings
    app_name: str = "FastAPI Demo"
    version: str = "0.2.0"
    environment: str = "development"

    # Database settings - support both SQLite (testing) and PostgreSQL (production)
    database_url: str = Field(default="sqlite+aiosqlite:///./test.db", validation_alias="DATABASE_URL")
    sqlalchemy_echo: bool = Field(default=False, validation_alias="SQLALCHEMY_ECHO")
    testing: bool = Field(default=False, validation_alias="TESTING")
    min_connections: int = 5
    max_connections: int = 20

    # Security settings
    allowed_hosts: List[str] = ["*"]
    cors_origins: List[str] = ["*"]

    # Rate limiting (requests per minute)
    rate_limit_window: int = Field(default=60)
    user_rate_limit: int = Field(default=100)
    manager_rate_limit: int = Field(default=300)
    admin_rate_limit: int = Field(default=1000)
    app_rate_limit: int = Field(default=5000)
    rate_limit_test: bool = Field(default=False, validation_alias="RATE_LIMIT_TEST")

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str = "app.log"

    # Production settings
    workers: int = Field(default=1, validation_alias="WORKERS")  # For gunicorn in production
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")

    # Kubernetes readiness/liveness probe settings
    readiness_path: str = "/health/check"
    liveness_path: str = "/health/check"

    # Kafka/Message Bus settings
    kafka_bootstrap_servers: str = Field(default="localhost:9092", validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_outbound_topic: str = Field(default="redox.outbound", validation_alias="KAFKA_OUTBOUND_TOPIC")
    kafka_dlq_topic: str = Field(default="redox.dlq", validation_alias="KAFKA_DLQ_TOPIC")
    kafka_consumer_group: str = Field(default="redox-gateway", validation_alias="KAFKA_CONSUMER_GROUP")

    # Redis settings for caching, rate limiting, and distributed features
    redis_url: str = Field(default="redis://localhost:6379", validation_alias="REDIS_URL")
    redis_enabled: bool = Field(default=True, validation_alias="REDIS_ENABLED")
    redis_ttl_default: int = Field(default=3600, validation_alias="REDIS_TTL_DEFAULT")  # 1 hour
    redis_ttl_rate_limit: int = Field(default=60, validation_alias="REDIS_TTL_RATE_LIMIT")  # 1 minute
    redis_ttl_session: int = Field(default=1800, validation_alias="REDIS_TTL_SESSION")  # 30 minutes
    redis_ttl_cache: int = Field(default=300, validation_alias="REDIS_TTL_CACHE")  # 5 minutes

    # External caller data source for DOB training pipeline
    caller_source_data: str = Field(default="", validation_alias="CALLER_SOURCE_DATA")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", protected_namespaces=())

    @property
    def is_testing(self) -> bool:
        """Used for database/environment testing"""
        return self.testing or self.environment == "test"

    @property
    def skip_rate_limit(self) -> bool:
        """Determines if rate limiting should be skipped"""
        # Only skip if explicitly told NOT to test rate limiting
        return self.is_testing and not self.rate_limit_test

    @property
    def rate_limit_enabled(self) -> bool:
        """Determines if rate limiting is enabled"""
        # Enable rate limiting in test mode when rate_limit_test is True
        return not self.skip_rate_limit

    def validate_db_url(self) -> None:
        """Validate database URL based on environment"""
        if not self.is_testing and self.database_url == "sqlite+aiosqlite:///./test.db":
            raise ValueError("Production DATABASE_URL must be set")

    # Override rate limits for testing
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.rate_limit_test:
            # Use stricter limits in test mode
            self.rate_limit_window = 1  # 1 second window
            self.user_rate_limit = 2  # 2 requests per second
            self.manager_rate_limit = 5  # 5 requests per second
            self.admin_rate_limit = 10  # 10 requests per second
            self.app_rate_limit = 20  # 20 requests per second


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance with validation"""
    settings = Settings()
    # Defensive: strip surrounding whitespace that may come from env or CI vars
    if isinstance(settings.database_url, str):
        settings.database_url = settings.database_url.strip()
    settings.validate_db_url()
    return settings
