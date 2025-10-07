from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application settings
    app_name: str = "FastAPI Demo"
    version: str = "0.2.0"
    environment: str = "development"

    # Database settings - preserve SQLite testing support
    database_url: str = "sqlite+aiosqlite:///./test.db"
    sqlalchemy_echo: bool = False
    testing: bool = False
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

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str = "app.log"

    # Testing flags
    testing_flag: bool = Field(default=False, validation_alias="TESTING")
    rate_limit_test: bool = Field(default=False, validation_alias="RATE_LIMIT_TEST")

    # Kafka/Message Bus settings
    kafka_bootstrap_servers: str = Field(default="localhost:9092", validation_alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_outbound_topic: str = Field(default="redox.outbound", validation_alias="KAFKA_OUTBOUND_TOPIC")
    kafka_dlq_topic: str = Field(default="redox.dlq", validation_alias="KAFKA_DLQ_TOPIC")
    kafka_consumer_group: str = Field(default="redox-gateway", validation_alias="KAFKA_CONSUMER_GROUP")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", protected_namespaces=())

    @property
    def is_testing(self) -> bool:
        """Used for database/environment testing"""
        return self.testing_flag or self.testing or self.environment == "test"

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
