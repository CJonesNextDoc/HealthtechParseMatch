from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",  # load variables from .env
        env_file_encoding="utf-8",
        extra="ignore"  # ignore unknown env vars
    )

    database_url: str
    sqlalchemy_echo: bool = False
    testing: bool = False  # can toggle test mode via TESTING=1

settings = Settings()